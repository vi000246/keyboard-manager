import sqlite3
from pathlib import Path

from backend.db.migrations import ensure_schema


def _table_names(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()


def _index_names(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        conn.close()


def test_creates_all_tables(tmp_path):
    db = tmp_path / "test.db"
    ensure_schema(db)
    assert {"events", "apps", "snapshots"} <= _table_names(db)


def test_idempotent(tmp_path):
    db = tmp_path / "test.db"
    ensure_schema(db)
    ensure_schema(db)  # second call must not raise


def test_indexes_present(tmp_path):
    db = tmp_path / "test.db"
    ensure_schema(db)
    idx = _index_names(db)
    assert "idx_events_app_key" in idx
    assert "idx_events_ts" in idx
    assert "idx_events_modifiers" in idx


def test_creates_parent_dir(tmp_path):
    db = tmp_path / "nested" / "sub" / "keystat.db"
    ensure_schema(db)
    assert db.exists()


def test_events_can_insert_with_defaults(tmp_path):
    db = tmp_path / "test.db"
    ensure_schema(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO events(ts, app_bundle, key, snapshot_id, source) "
            "VALUES(?, ?, ?, ?, ?)",
            (100, "com.example.app", "j", 0, "test"),
        )
        conn.commit()
        row = conn.execute("SELECT modifiers, count FROM events").fetchone()
        assert row == ("", 1)  # default modifiers='', count=1
    finally:
        conn.close()
