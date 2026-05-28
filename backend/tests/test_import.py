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


def test_reimport_replaces_existing_source_by_default(db, tmp_path):
    """Re-importing same source must replace, not duplicate."""
    sample = tmp_path / "k.json"
    sample.write_text(json.dumps({"com.foo": {"j": 100, "k": 50}}))
    import_file(sample, db)

    # Simulate HS keystat counts having grown since last import.
    sample.write_text(json.dumps({"com.foo": {"j": 200, "k": 75, "l": 10}}))
    import_file(sample, db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        # Total events should reflect the LATER import only, not sum of both.
        j = conn.execute(
            "SELECT count FROM events WHERE app_bundle='com.foo' AND key='j'"
        ).fetchall()
        assert len(j) == 1, f"j duplicated: {[dict(r) for r in j]}"
        assert j[0]["count"] == 200

        all_keys = {
            r["key"] for r in conn.execute("SELECT key FROM events").fetchall()
        }
        assert all_keys == {"j", "k", "l"}

        # Only one snapshot of hs_keystat_json should remain.
        snaps = conn.execute(
            "SELECT * FROM snapshots WHERE source='hs_keystat_json'"
        ).fetchall()
        assert len(snaps) == 1
    finally:
        conn.close()


def test_reimport_append_mode_preserves_history(db, tmp_path):
    """Explicit append mode keeps both snapshots (advanced use)."""
    sample = tmp_path / "k.json"
    sample.write_text(json.dumps({"com.foo": {"j": 5}}))
    import_file(sample, db)
    import_file(sample, db, replace_existing_source=False)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT count FROM events WHERE key='j' ORDER BY count"
        ).fetchall()
        assert len(rows) == 2  # two events, would sum to 10 via top_n
        snaps = conn.execute(
            "SELECT COUNT(*) AS n FROM snapshots WHERE source='hs_keystat_json'"
        ).fetchone()
        assert snaps["n"] == 2
    finally:
        conn.close()


def test_reimport_does_not_touch_other_sources(db, tmp_path):
    """Replacing 'hs_keystat_json' must not delete native_helper events."""
    sample = tmp_path / "k.json"
    sample.write_text(json.dumps({"com.foo": {"j": 5}}))
    import_file(sample, db)

    # Simulate a helper-written row using a different source label.
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (100, "com.foo", "j", "", 1, 999, "native_helper"),
        )
        conn.commit()
    finally:
        conn.close()

    import_file(sample, db)  # re-import; should NOT touch native_helper rows

    conn = sqlite3.connect(db)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM events WHERE source='native_helper'"
        ).fetchone()[0]
        assert n == 1
    finally:
        conn.close()
