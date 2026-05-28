"""Tests for the batched SQLite EventSink.

We import the schema helper from the backend package so the sink writes
against the real production schema, not a re-declared one.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

# Add project root so `from backend.db.migrations import ensure_schema` resolves.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.migrations import ensure_schema  # noqa: E402
from native_helper.sink import EventSink, open_snapshot  # noqa: E402


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    ensure_schema(p)
    return p


def _rows(db, sql, params=()):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def test_record_then_flush_writes_events(db):
    sn = open_snapshot(db, "test")
    sink = EventSink(db, source="test", flush_interval=999)
    sink.start(snapshot_id=sn)
    sink.record(key="j", modifiers="", app_bundle="appA", ts=100)
    sink.record(key="k", modifiers="", app_bundle="appA", ts=101)
    n = sink.flush_now()
    assert n == 2
    rows = _rows(db, "SELECT * FROM events ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["key"] == "j" and rows[0]["count"] == 1
    assert rows[0]["snapshot_id"] == sn
    assert rows[0]["source"] == "test"


def test_record_without_start_raises(db):
    sink = EventSink(db, source="test")
    with pytest.raises(RuntimeError):
        sink.record(key="j", modifiers="", app_bundle="appA", ts=100)


def test_flush_now_returns_zero_when_empty(db):
    sn = open_snapshot(db, "test")
    sink = EventSink(db, source="test", flush_interval=999)
    sink.start(snapshot_id=sn)
    assert sink.flush_now() == 0


def test_stop_flushes_remaining_buffer(db):
    sn = open_snapshot(db, "test")
    sink = EventSink(db, source="test", flush_interval=999)
    sink.start(snapshot_id=sn)
    sink.record(key="j", modifiers="", app_bundle="appA", ts=100)
    sink.stop()
    assert len(_rows(db, "SELECT * FROM events")) == 1


def test_carries_modifier_string(db):
    sn = open_snapshot(db, "test")
    sink = EventSink(db, source="test", flush_interval=999)
    sink.start(snapshot_id=sn)
    sink.record(key="v", modifiers="cmd", app_bundle="appA", ts=100)
    sink.flush_now()
    row = _rows(db, "SELECT * FROM events")[0]
    assert row["modifiers"] == "cmd"


def test_open_snapshot_returns_increasing_ids(db):
    a = open_snapshot(db, "test", notes="first")
    b = open_snapshot(db, "test", notes="second")
    assert b > a
    rows = _rows(db, "SELECT * FROM snapshots ORDER BY id")
    assert rows[0]["notes"] == "first"
    assert rows[1]["notes"] == "second"
