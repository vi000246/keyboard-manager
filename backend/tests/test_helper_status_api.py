"""Tests for /api/helper/status.

The helper isn't running in the test environment, so the probe will fail —
we monkeypatch `_probe_helper` to make the contract testable independently.
"""
import importlib
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db.migrations import ensure_schema

FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    ensure_schema(db)
    monkeypatch.setenv("VIAL_PATH", str(FIXTURE))
    monkeypatch.setenv("DB_PATH", str(db))
    from backend.api import layout as layout_mod
    layout_mod._cache.clear()
    from backend import main as backend_main
    importlib.reload(backend_main)
    return TestClient(backend_main.app), db


async def _stub_running():
    return True


async def _stub_down():
    return False


def _insert_event(db: Path, ts: int) -> None:
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (ts, "test.app", "j", "", 1, 0, "native_helper"),
        )
        conn.commit()
    finally:
        conn.close()


def test_status_disconnected_when_probe_fails(client, monkeypatch):
    c, _ = client
    from backend.api import helper as helper_mod
    monkeypatch.setattr(helper_mod, "_probe_helper", _stub_down)
    r = c.get("/api/helper/status")
    assert r.status_code == 200
    body = r.json()
    assert body["process_running"] is False
    assert body["recently_captured"] is False


def test_status_active_when_recent_event(client, monkeypatch):
    c, db = client
    _insert_event(db, int(time.time()))
    from backend.api import helper as helper_mod
    monkeypatch.setattr(helper_mod, "_probe_helper", _stub_running)
    body = c.get("/api/helper/status").json()
    assert body["process_running"] is True
    assert body["recently_captured"] is True
    assert body["last_event_ts"] is not None
    assert body["seconds_since_last_event"] is not None
    assert body["seconds_since_last_event"] < 60


def test_status_idle_when_event_is_stale(client, monkeypatch):
    c, db = client
    # 1 hour ago — beyond the 5-minute recent window
    _insert_event(db, int(time.time()) - 3600)
    from backend.api import helper as helper_mod
    monkeypatch.setattr(helper_mod, "_probe_helper", _stub_running)
    body = c.get("/api/helper/status").json()
    assert body["process_running"] is True
    assert body["recently_captured"] is False
    assert body["seconds_since_last_event"] >= 3600


def test_status_no_events_yet(client, monkeypatch):
    c, _ = client
    from backend.api import helper as helper_mod
    monkeypatch.setattr(helper_mod, "_probe_helper", _stub_running)
    body = c.get("/api/helper/status").json()
    assert body["process_running"] is True
    assert body["last_event_ts"] is None
    assert body["seconds_since_last_event"] is None
    assert body["recently_captured"] is False


def test_status_includes_recent_window(client, monkeypatch):
    c, _ = client
    from backend.api import helper as helper_mod
    monkeypatch.setattr(helper_mod, "_probe_helper", _stub_down)
    body = c.get("/api/helper/status").json()
    assert body["recent_window_sec"] == 300  # default 5 min
