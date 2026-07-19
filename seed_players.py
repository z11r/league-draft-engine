"""Seed the players table with the high-elo player pool for one platform.

Usage:
    python seed_players.py --platform na1
    python seed_players.py --platform euw1 --tiers challenger,grandmaster,master

One API request per tier — the apex league endpoints return every player in
the league at once. Re-running is safe: existing players are left untouched.
"""

import argparse

from db import connect
from riot_api import RiotClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, help="e.g. na1, euw1, kr")
    parser.add_argument(
        "--tiers",
        default="challenger,grandmaster",
        help="comma-separated: challenger,grandmaster,master",
    )
    args = parser.parse_args()

    client = RiotClient(args.platform)
    conn = connect()

    for tier in args.tiers.split(","):
        entries = client.league_entries(tier)
        conn.executemany(
            "INSERT OR IGNORE INTO players (puuid, platform, tier) VALUES (?, ?, ?)",
            [(e["puuid"], args.platform, tier) for e in entries],
        )
        conn.commit()
        print(f"{args.platform} {tier}: {len(entries)} players")

    total = conn.execute(
        "SELECT COUNT(*) FROM players WHERE platform = ?", (args.platform,)
    ).fetchone()[0]
    print(f"{args.platform} player pool: {total}")


if __name__ == "__main__":
    main()
