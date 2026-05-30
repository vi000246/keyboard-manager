"""SQLite schema migrations — idempotent boot-time table creation.

Schema follows `docs/spec/keyboard-manager.spec.md` §Data Model. We use raw SQL
+ `CREATE IF NOT EXISTS` instead of an ORM because the schema is small and
single-writer (one helper, one importer).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER NOT NULL,
  app_bundle  TEXT    NOT NULL,
  key         TEXT    NOT NULL,
  modifiers   TEXT    NOT NULL DEFAULT '',
  count       INTEGER NOT NULL DEFAULT 1,
  snapshot_id INTEGER NOT NULL,
  source      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_app_key   ON events(app_bundle, key);
CREATE INDEX IF NOT EXISTS idx_events_modifiers ON events(modifiers);
CREATE INDEX IF NOT EXISTS idx_events_ts        ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_snapshot  ON events(snapshot_id);

CREATE TABLE IF NOT EXISTS apps (
  bundle_id     TEXT    PRIMARY KEY,
  display_name  TEXT,
  bucket        TEXT,
  first_seen_ts INTEGER NOT NULL,
  last_seen_ts  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  ts     INTEGER NOT NULL,
  source TEXT    NOT NULL,
  notes  TEXT
);

-- User-defined names for keycodes / actions. `raw` is the keycode string as it
-- appears in /api/layout (e.g. "LALT(KC_F)", "TD(4)", or a combo output). The
-- name ("全螢幕") is shown across the viewer pages to replace/annotate the code.
CREATE TABLE IF NOT EXISTS key_aliases (
  raw  TEXT PRIMARY KEY,
  name TEXT NOT NULL
);
"""


def ensure_schema(db_path: Path) -> None:
    """Create tables and indexes if missing. Safe to call repeatedly."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
