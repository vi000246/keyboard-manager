import sqlite3
from pathlib import Path

import pytest

from backend.db.migrations import ensure_schema
from backend.db.repository import AppsRepo, SnapshotRepo, StatsRepo


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "t.db"
    ensure_schema(p)
    return p


def _insert_events(db: Path, rows: list[tuple]) -> None:
    """rows: (ts, app_bundle, key, modifiers, count, snapshot_id, source)"""
    conn = sqlite3.connect(db)
    try:
        conn.executemany(
            "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
            "VALUES(?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def test_snapshot_create_and_fetch(db):
    sn = SnapshotRepo(db)
    sid = sn.create(ts=100, source="test", notes="x")
    assert sid > 0
    row = sn.get(sid)
    assert row is not None
    assert row["ts"] == 100
    assert row["source"] == "test"
    assert row["notes"] == "x"


def test_snapshot_get_missing_returns_none(db):
    sn = SnapshotRepo(db)
    assert sn.get(999) is None


def test_apps_upsert_creates_then_updates(db):
    apps = AppsRepo(db)
    apps.upsert("com.foo.app", display_name="Foo", bucket="terminal", ts=100)
    apps.upsert("com.foo.app", display_name="Foo", bucket="terminal", ts=200)
    row = apps.get("com.foo.app")
    assert row["first_seen_ts"] == 100
    assert row["last_seen_ts"] == 200
    assert row["bucket"] == "terminal"


def test_apps_upsert_preserves_existing_bucket_if_new_is_null(db):
    apps = AppsRepo(db)
    apps.upsert("com.foo.app", display_name="Foo", bucket="terminal", ts=100)
    apps.upsert("com.foo.app", display_name=None, bucket=None, ts=200)
    row = apps.get("com.foo.app")
    assert row["bucket"] == "terminal"  # not overwritten with NULL


def test_apps_all_sorted(db):
    apps = AppsRepo(db)
    apps.upsert("z.app", None, None, 100)
    apps.upsert("a.app", None, None, 100)
    all_apps = apps.all()
    assert [a["bundle_id"] for a in all_apps] == ["a.app", "z.app"]


def test_stats_top_n_empty(db):
    s = StatsRepo(db)
    assert s.top_n(app=None, kind="single", n=10) == []


def test_stats_top_n_single_aggregates(db):
    s = StatsRepo(db)
    _insert_events(db, [
        (100, "appA", "j", "", 5, 1, "t"),
        (100, "appA", "j", "", 3, 1, "t"),
        (100, "appA", "k", "", 2, 1, "t"),
        (100, "appA", "v", "cmd", 4, 1, "t"),
    ])
    rows = s.top_n(app="appA", kind="single", n=10)
    assert rows[0]["key"] == "j" and rows[0]["total"] == 8
    assert rows[1]["key"] == "k" and rows[1]["total"] == 2
    assert all(r["modifiers"] == "" for r in rows)


def test_stats_top_n_mod_filter(db):
    s = StatsRepo(db)
    _insert_events(db, [
        (100, "appA", "v", "cmd", 5, 1, "t"),
        (100, "appA", "v", "", 100, 1, "t"),  # should NOT appear under kind=mod
    ])
    rows = s.top_n(app="appA", kind="mod", n=10)
    assert len(rows) == 1
    assert rows[0]["key"] == "v"
    assert rows[0]["modifiers"] == "cmd"


def test_stats_top_n_all_kind(db):
    s = StatsRepo(db)
    _insert_events(db, [
        (100, "appA", "v", "cmd", 5, 1, "t"),
        (100, "appA", "j", "", 8, 1, "t"),
    ])
    rows = s.top_n(app="appA", kind="all", n=10)
    assert len(rows) == 2


def test_stats_total_count(db):
    s = StatsRepo(db)
    _insert_events(db, [
        (100, "appA", "j", "", 5, 1, "t"),
        (100, "appB", "k", "", 7, 1, "t"),
    ])
    assert s.total_count() == 12
    assert s.total_count(app="appA") == 5


def test_stats_global_no_app_filter(db):
    s = StatsRepo(db)
    _insert_events(db, [
        (100, "appA", "j", "", 5, 1, "t"),
        (100, "appB", "j", "", 3, 1, "t"),
    ])
    rows = s.top_n(app=None, kind="single", n=10)
    # Same key across apps stays separate (group by key+modifiers, not app)
    j_total = sum(r["total"] for r in rows if r["key"] == "j")
    assert j_total == 8
