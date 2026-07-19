"""Continuous match collector. Run one process per platform:

    python collector.py --platform na1

Loops forever, alternating two phases:
  1. scan:  for each seeded player not scanned recently, fetch their recent
            ranked match ids and add unseen ones to the match_ids queue
  2. drain: fetch every queued match, validate it, extract the draft
            (10 champions by role + winner + patch) into the matches table

Every unit of work is committed individually, so killing the process at any
point loses at most one match — restart and it resumes where it left off.
"""

import argparse
import json
import sys
import time
import zlib

from db import connect
from riot_api import RiotClient

RESCAN_HOURS = 12  # how often to re-check a player for new matches

ROLE_MAP = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "mid",
    "BOTTOM": "bot",
    "UTILITY": "support",
}


def extract(match: dict) -> dict | None:
    """Flatten raw match JSON into one training row, or None if unusable."""
    info = match["info"]
    if info.get("queueId") != 420:
        return None
    if info.get("gameDuration", 0) < 300:  # remakes end before 5 minutes
        return None

    # gameVersion looks like "16.13.693.1234" -> patch "16.13"
    patch = ".".join(info["gameVersion"].split(".")[:2])

    slots: dict[str, str] = {}
    for p in info["participants"]:
        side = "blue" if p["teamId"] == 100 else "red"
        role = ROLE_MAP.get(p.get("teamPosition", ""))
        if role is None:
            return None  # missing/unknown role assignment
        key = f"{side}_{role}"
        if key in slots:
            return None  # two players assigned the same role
        slots[key] = p["championName"]
    if len(slots) != 10:
        return None

    blue_win = next(t["win"] for t in info["teams"] if t["teamId"] == 100)
    return {
        "match_id": match["metadata"]["matchId"],
        "patch": patch,
        "game_creation": info["gameCreation"],
        "blue_win": int(blue_win),
        **slots,
    }


def scan_players(conn, client: RiotClient) -> None:
    rows = conn.execute(
        """SELECT puuid FROM players
           WHERE platform = ?
             AND (last_scanned IS NULL
                  OR last_scanned < datetime('now', ?))""",
        (client.platform, f"-{RESCAN_HOURS} hours"),
    ).fetchall()
    if not rows:
        return
    print(f"[scan] {len(rows)} players due")
    for i, (puuid,) in enumerate(rows, 1):
        ids = client.match_ids(puuid)
        conn.executemany(
            "INSERT OR IGNORE INTO match_ids (match_id, platform) VALUES (?, ?)",
            [(m, client.platform) for m in ids],
        )
        conn.execute(
            "UPDATE players SET last_scanned = datetime('now') WHERE puuid = ?",
            (puuid,),
        )
        conn.commit()
        if i % 50 == 0:
            queued = conn.execute(
                "SELECT COUNT(*) FROM match_ids WHERE platform = ? AND status = 0",
                (client.platform,),
            ).fetchone()[0]
            print(f"[scan] {i}/{len(rows)} players, {queued} matches queued")


def drain_queue(conn, client: RiotClient) -> None:
    rows = conn.execute(
        "SELECT match_id FROM match_ids WHERE platform = ? AND status = 0",
        (client.platform,),
    ).fetchall()
    if not rows:
        return
    print(f"[drain] {len(rows)} matches queued")
    for i, (match_id,) in enumerate(rows, 1):
        data = client.match(match_id)
        row = extract(data)
        if row is None:
            conn.execute(
                "UPDATE match_ids SET status = -1 WHERE match_id = ?", (match_id,)
            )
        else:
            row["raw_json"] = zlib.compress(json.dumps(data).encode())
            conn.execute(
                """INSERT OR IGNORE INTO matches
                   (match_id, patch, game_creation,
                    blue_top, blue_jungle, blue_mid, blue_bot, blue_support,
                    red_top, red_jungle, red_mid, red_bot, red_support,
                    blue_win, raw_json)
                   VALUES (:match_id, :patch, :game_creation,
                           :blue_top, :blue_jungle, :blue_mid, :blue_bot, :blue_support,
                           :red_top, :red_jungle, :red_mid, :red_bot, :red_support,
                           :blue_win, :raw_json)""",
                row,
            )
            conn.execute(
                "UPDATE match_ids SET status = 1 WHERE match_id = ?", (match_id,)
            )
        conn.commit()
        if i % 100 == 0:
            total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            print(f"[drain] {i}/{len(rows)} fetched, {total} matches stored total")


def main() -> None:
    # flush prints per line even when stdout is a log file, so
    # `tail -f` shows live progress and a killed process loses nothing
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, help="e.g. na1, euw1, kr")
    args = parser.parse_args()

    client = RiotClient(args.platform)
    conn = connect()
    print(f"collector running for {args.platform} (ctrl-c to stop)")
    while True:
        scan_players(conn, client)
        drain_queue(conn, client)
        time.sleep(60)


if __name__ == "__main__":
    main()
