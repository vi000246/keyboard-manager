"""Tests for the /api/layout/upload endpoint and the uploaded-file precedence."""
import importlib
import io
import json
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
    return TestClient(backend_main.app), tmp_path


def _multipart(content: bytes, name: str = "test.vil"):
    return {"file": (name, io.BytesIO(content), "application/octet-stream")}


def test_source_reports_default_when_no_upload(client):
    c, _ = client
    body = c.get("/api/layout/source").json()
    assert body["is_uploaded"] is False
    assert body["active_path"] == body["default_path"]


def test_upload_replaces_active_layout(client):
    c, tmp_path = client
    payload = FIXTURE.read_bytes()
    r = c.post("/api/layout/upload", files=_multipart(payload, "new.vil"))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["filename"] == "new.vil"
    assert (tmp_path / "uploaded.vil").exists()

    source = c.get("/api/layout/source").json()
    assert source["is_uploaded"] is True
    assert source["active_path"].endswith("uploaded.vil")


def test_upload_rejects_invalid_vial(client):
    c, _ = client
    r = c.post("/api/layout/upload", files=_multipart(b"{not valid json"))
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "VIAL_PARSE_ERROR"

    # Default is still active after a failed upload
    source = c.get("/api/layout/source").json()
    assert source["is_uploaded"] is False


def test_upload_rejects_too_large_file(client):
    c, _ = client
    # > 1 MiB
    huge = b"{" + b"x" * (1024 * 1024 + 100) + b"}"
    r = c.post("/api/layout/upload", files=_multipart(huge))
    assert r.status_code == 422
    assert "too large" in r.json()["detail"]["message"]


def test_upload_then_layout_uses_new_file(client):
    c, _ = client
    # Build a tiny but valid Vial file with a single layer
    custom = {
        "vial_protocol": 6, "version": 1, "uid": 42,
        "layout": [
            [
                ["KC_A", "KC_B", "KC_C", "KC_D", "KC_E", "KC_F", -1],
            ] + [[-1] * 7] * 9
        ] + [[[-1] * 7] * 10] * 5,
        "tap_dance": [], "combo": [],
    }
    body = json.dumps(custom).encode("utf-8")
    r = c.post("/api/layout/upload", files=_multipart(body, "custom.vil"))
    assert r.status_code == 200

    layout = c.get("/api/layout").json()
    assert layout["uid"] == 42
    assert layout["layers"][0]["rows"][0]["keys"][0]["raw"] == "KC_A"


def test_revert_removes_upload(client):
    c, tmp_path = client
    # First upload something
    c.post("/api/layout/upload", files=_multipart(FIXTURE.read_bytes()))
    assert (tmp_path / "uploaded.vil").exists()

    # Then revert
    r = c.delete("/api/layout/upload")
    assert r.status_code == 200
    assert r.json()["reverted"] is True
    assert not (tmp_path / "uploaded.vil").exists()

    source = c.get("/api/layout/source").json()
    assert source["is_uploaded"] is False


def test_revert_when_nothing_uploaded(client):
    c, _ = client
    r = c.delete("/api/layout/upload")
    assert r.status_code == 200
    assert r.json()["reverted"] is False
