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


# ─── Data-preservation safety net ──────────────────────────────────────
#
# These tests encode the contract: future migrations MUST stay additive.
# The live capture has been accumulating events that cannot be reproduced;
# a `DROP TABLE` or `DELETE FROM` in the migration would silently wipe
# everything on the next container restart. If you need a non-additive
# schema change in the future, write it as an explicit one-shot script
# with a backup step, NOT by editing SCHEMA.


def test_schema_text_contains_no_destructive_statements():
    """Hard-fail if anyone adds DROP / DELETE / TRUNCATE to the migration."""
    from backend.db import migrations

    schema = migrations.SCHEMA.upper()
    for forbidden in ("DROP TABLE", "DROP INDEX", "DELETE FROM", "TRUNCATE"):
        assert forbidden not in schema, (
            f"{forbidden} is forbidden in db/migrations.py SCHEMA — "
            "see docs/data-preservation.md"
        )


def test_schema_uses_if_not_exists_for_every_create():
    """Every CREATE must be guarded so reruns don't clobber existing data."""
    from backend.db import migrations

    schema = migrations.SCHEMA.upper()
    create_count = schema.count("CREATE ")
    guarded = schema.count("CREATE TABLE IF NOT EXISTS") + schema.count(
        "CREATE INDEX IF NOT EXISTS"
    )
    assert create_count == guarded, (
        f"every CREATE must be CREATE IF NOT EXISTS (found {create_count} "
        f"CREATEs but only {guarded} guarded)"
    )


# ─── events_agg aggregation mirror ─────────────────────────────────────


def test_events_agg_trigger_maintains_counts(tmp_path):
    """Every insert into events must be reflected in events_agg, summed by
    (app_bundle, key, modifiers) — this is what all stats reads rely on."""
    db = tmp_path / "test.db"
    ensure_schema(db)
    conn = sqlite3.connect(db)
    try:
        conn.executemany(
            "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            [
                (100, "com.foo", "j", "",    1, 1, "t"),
                (101, "com.foo", "j", "",    2, 1, "t"),
                (102, "com.foo", "v", "cmd", 1, 1, "t"),
                (103, "com.bar", "j", "",    1, 1, "t"),
            ],
        )
        conn.commit()
        rows = conn.execute(
            "SELECT app_bundle, key, modifiers, count FROM events_agg "
            "ORDER BY app_bundle, key, modifiers"
        ).fetchall()
        assert rows == [
            ("com.bar", "j", "", 1),
            ("com.foo", "j", "", 3),
            ("com.foo", "v", "cmd", 1),
        ]
    finally:
        conn.close()


def test_events_agg_backfilled_for_preexisting_events(tmp_path):
    """Upgrade path: a live DB that accumulated events before events_agg
    existed must get a one-shot backfill when ensure_schema next runs."""
    db = tmp_path / "test.db"
    ensure_schema(db)

    # Simulate the legacy state: events present, but no trigger / agg rows.
    conn = sqlite3.connect(db)
    try:
        conn.execute("DROP TRIGGER trg_events_agg_insert")
        conn.execute("DELETE FROM events_agg")
        conn.executemany(
            "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            [
                (100, "com.foo", "j", "", 1, 1, "t"),
                (101, "com.foo", "j", "", 1, 1, "t"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    ensure_schema(db)

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT app_bundle, key, modifiers, count FROM events_agg"
        ).fetchall()
        assert rows == [("com.foo", "j", "", 2)]
        # And the freshly re-created trigger keeps maintaining it.
        conn.execute(
            "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
            "VALUES(102, 'com.foo', 'j', '', 1, 1, 't')"
        )
        conn.commit()
        total = conn.execute(
            "SELECT count FROM events_agg WHERE key='j'"
        ).fetchone()[0]
        assert total == 3
    finally:
        conn.close()


def test_ensure_schema_on_populated_db_preserves_rows(tmp_path):
    """The high-value contract: running ensure_schema() on a database that
    already has live capture events must NOT touch those rows. This is the
    scenario every container restart / image rebuild goes through."""
    db = tmp_path / "test.db"
    ensure_schema(db)

    conn = sqlite3.connect(db)
    try:
        conn.executemany(
            "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            [
                (100, "com.foo", "j", "",    1, 1, "native_helper"),
                (101, "com.foo", "k", "",    1, 1, "native_helper"),
                (102, "com.foo", "v", "cmd", 1, 1, "native_helper"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    # Simulate three back-to-back container restarts.
    for _ in range(3):
        ensure_schema(db)

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT key, modifiers, source FROM events ORDER BY id"
        ).fetchall()
        assert rows == [
            ("j", "",    "native_helper"),
            ("k", "",    "native_helper"),
            ("v", "cmd", "native_helper"),
        ]
    finally:
        conn.close()
