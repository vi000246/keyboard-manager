import json
import sqlite3
from pathlib import Path

import pytest

from backend.db.migrations import ensure_schema
from backend.scripts.import_keystat import import_file


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "t.db"
    ensure_schema(p)
    return p


def test_import_minimal(db, tmp_path):
    sample = tmp_path / "sample.json"
    sample.write_text(
        json.dumps(
            {
                "__meta": {
                    "startedAt": "2026-05-20T06:10:12Z",
                    "lastFlush": "2026-05-28T05:57:03Z",
                },
                "com.googlecode.iterm2": {"j": 5892, "cmd+v": 3, "return": 14},
                "com.brave.Browser": {"right": 2497, "cmd+1": 1529},
            }
        )
    )
    result = import_file(sample, db)
    assert result["events"] == 5
    assert result["apps"] == 2
    assert result["snapshot_id"] > 0

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        j_row = conn.execute(
            "SELECT * FROM events WHERE app_bundle='com.googlecode.iterm2' AND key='j'"
        ).fetchone()
        assert j_row["count"] == 5892
        assert j_row["modifiers"] == ""

        cmdv_row = conn.execute(
            "SELECT * FROM events WHERE key='v' AND modifiers='cmd'"
        ).fetchone()
        assert cmdv_row["count"] == 3

        iterm_app = conn.execute(
            "SELECT * FROM apps WHERE bundle_id='com.googlecode.iterm2'"
        ).fetchone()
        assert iterm_app["bucket"] == "terminal"

        brave_app = conn.execute(
            "SELECT * FROM apps WHERE bundle_id='com.brave.Browser'"
        ).fetchone()
        assert brave_app["bucket"] == "browser"
    finally:
        conn.close()


def test_import_skips_meta_and_non_dict_values(db, tmp_path):
    sample = tmp_path / "weird.json"
    sample.write_text(
        json.dumps(
            {
                "__meta": {"x": 1},
                "com.foo": {"a": 5},
                "not_a_dict_value": "ignored",
            }
        )
    )
    result = import_file(sample, db)
    assert result["events"] == 1
    assert result["apps"] == 1


def test_import_unknown_bundle_gets_null_bucket(db, tmp_path):
    sample = tmp_path / "unk.json"
    sample.write_text(json.dumps({"com.unknown.thing": {"a": 1}}))
    import_file(sample, db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM apps WHERE bundle_id='com.unknown.thing'"
        ).fetchone()
        assert row["bucket"] is None
    finally:
        conn.close()


def test_import_multi_mod_serializes_sorted(db, tmp_path):
    sample = tmp_path / "multi.json"
    sample.write_text(json.dumps({"com.foo": {"cmd+ctrl+alt+space": 7}}))
    import_file(sample, db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM events WHERE key='space'").fetchone()
        # Alphabetical sort: alt+cmd+ctrl
        assert row["modifiers"] == "alt+cmd+ctrl"
        assert row["count"] == 7
    finally:
        conn.close()


def test_import_creates_snapshot_with_source(db, tmp_path):
    sample = tmp_path / "snap.json"
    sample.write_text(json.dumps({"com.foo": {"a": 1}}))
    result = import_file(sample, db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        snap = conn.execute(
            "SELECT * FROM snapshots WHERE id=?", (result["snapshot_id"],)
        ).fetchone()
        assert snap["source"] == "hs_keystat_json"
        assert "snap.json" in (snap["notes"] or "")
    finally:
        conn.close()


def test_import_full_baseline_count(db):
    """Import the real ~/keystat-counts.json if present. Tolerant check."""
    src = Path.home() / "keystat-counts.json"
    if not src.exists():
        pytest.skip("baseline json missing on this machine")
    result = import_file(src, db)
    # 8 days of data should always have thousands of (app, key) pairs
    assert result["events"] > 100
    assert result["apps"] > 5
