"""SQLite storage for the collection pipeline.

Three tables, one per pipeline stage:
  players   -> who we track (high-elo puuids)
  match_ids -> work queue of matches we know about but haven't fetched
  matches   -> the training data: one row per game, one column per draft slot
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "league.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    puuid        TEXT PRIMARY KEY,
    platform     TEXT NOT NULL,
    tier         TEXT NOT NULL,
    last_scanned TEXT
);

CREATE TABLE IF NOT EXISTS match_ids (
    match_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    -- 0 = queued, 1 = fetched and stored, -1 = fetched but rejected (remake,
    -- wrong queue, missing role data). Rejected ids stay here so we never
    -- spend a request re-fetching them.
    status   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS matches (
    match_id      TEXT PRIMARY KEY,
    patch         TEXT NOT NULL,
    game_creation INTEGER NOT NULL,
    blue_top TEXT NOT NULL, blue_jungle TEXT NOT NULL, blue_mid TEXT NOT NULL,
    blue_bot TEXT NOT NULL, blue_support TEXT NOT NULL,
    red_top  TEXT NOT NULL, red_jungle  TEXT NOT NULL, red_mid  TEXT NOT NULL,
    red_bot  TEXT NOT NULL, red_support TEXT NOT NULL,
    blue_win INTEGER NOT NULL,
    raw_json BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_match_ids_status ON match_ids (platform, status);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.executescript(SCHEMA)
    return conn
