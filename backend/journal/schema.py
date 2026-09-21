"""SQLite schema for ops trade journal."""
from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    pair TEXT NOT NULL,
    setup_id INTEGER,
    setup_name TEXT,
    direction TEXT NOT NULL,
    entry REAL,
    sl REAL,
    tp REAL,
    confluence_score REAL,
    outcome TEXT,
    reason_code TEXT,
    note TEXT,
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    net_pnl REAL,
    r_multiple REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_dedupe
ON trades(source, pair, setup_id, entry_time, direction);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
