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

-- Pre-aggregated mirror of `events`, maintained by trigger. All stats reads
-- (top-N, totals, heatmap, nameable) hit this table so query cost stays
-- O(distinct combos) instead of O(total keystrokes). `events` remains the
-- raw append-only log for future time-based analysis.
CREATE TABLE IF NOT EXISTS events_agg (
  app_bundle TEXT    NOT NULL,
  key        TEXT    NOT NULL,
  modifiers  TEXT    NOT NULL DEFAULT '',
  count      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (app_bundle, key, modifiers)
) WITHOUT ROWID;
"""

# Created outside SCHEMA: trigger existence doubles as the "backfill already
# ran" marker, so it must be created in the SAME transaction as the backfill
# (see _ensure_agg_trigger) — otherwise a concurrent writer could slip an
# event in between trigger creation and backfill and get double-counted.
_AGG_TRIGGER_NAME = "trg_events_agg_insert"
_AGG_TRIGGER_SQL = f"""
CREATE TRIGGER {_AGG_TRIGGER_NAME} AFTER INSERT ON events BEGIN
  INSERT INTO events_agg(app_bundle, key, modifiers, count)
  VALUES (NEW.app_bundle, NEW.key, NEW.modifiers, NEW.count)
  ON CONFLICT(app_bundle, key, modifiers)
  DO UPDATE SET count = count + excluded.count;
END;
"""

_AGG_BACKFILL_SQL = """
INSERT INTO events_agg(app_bundle, key, modifiers, count)
SELECT app_bundle, key, modifiers, SUM(count)
FROM events
GROUP BY app_bundle, key, modifiers
"""


def ensure_schema(db_path: Path) -> None:
    """Create tables and indexes if missing. Safe to call repeatedly.

    NOTE on journal mode: this DB is written by the native helper on the macOS
    host AND read by the backend inside Docker via a VirtioFS bind mount. WAL
    requires shared-memory coherence between all connected processes (same
    kernel), which a host↔VM mount cannot guarantee — so we deliberately stay
    on the default rollback journal. Python's sqlite3 default busy timeout
    (5s) absorbs the brief writer locks from the helper's 5s batch flushes.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _ensure_agg_trigger(conn)
    finally:
        conn.close()


def _ensure_agg_trigger(conn: sqlite3.Connection) -> None:
    """Create the events→events_agg trigger and backfill, atomically.

    BEGIN IMMEDIATE serializes concurrent boots (helper + backend both call
    ensure_schema); the loser re-checks and finds the trigger already there.
    Any event insert either commits before this transaction (and is captured
    by the backfill SELECT) or after it (and fires the trigger) — never both.
    """
    trigger_exists_sql = (
        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?"
    )
    if conn.execute(trigger_exists_sql, (_AGG_TRIGGER_NAME,)).fetchone():
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not conn.execute(trigger_exists_sql, (_AGG_TRIGGER_NAME,)).fetchone():
            conn.execute(_AGG_TRIGGER_SQL)
            conn.execute("DELETE FROM events_agg")
            conn.execute(_AGG_BACKFILL_SQL)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
