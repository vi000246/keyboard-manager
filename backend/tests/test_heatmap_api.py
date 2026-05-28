import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db.migrations import ensure_schema
from backend.scripts.import_keystat import import_file

FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    ensure_schema(db)
    sample = tmp_path / "k.json"
    sample.write_text(
        json.dumps(
            {
                "__meta": {},
                "com.googlecode.iterm2": {"j": 5892, "k": 2314, "f19": 1201},
                "com.brave.Browser": {"right": 2497},
            }
        )
    )
    import_file(sample, db)
    monkeypatch.setenv("VIAL_PATH", str(FIXTURE))
    monkeypatch.setenv("DB_PATH", str(db))
    from backend.api import layout as layout_mod
    layout_mod._cache.clear()
    from backend import main as backend_main
    importlib.reload(backend_main)
    return TestClient(backend_main.app)


def test_heatmap_returns_cells_and_unmapped(client):
    r = client.get("/api/stats/heatmap")
    assert r.status_code == 200
    body = r.json()
    assert "cells" in body
    assert "unmapped" in body
    assert "max_count" in body
    assert "coverage_pct" in body


def test_heatmap_j_mapped_to_base(client):
    body = client.get("/api/stats/heatmap").json()
    j_cell = next(c for c in body["cells"] if c["key"] == "J")
    assert j_cell["layer"] == 0
    assert j_cell["count"] == 5892


def test_heatmap_f19_unmapped(client):
    body = client.get("/api/stats/heatmap").json()
    f19 = next((u for u in body["unmapped"] if u["key"] == "f19"), None)
    assert f19 is not None
    assert f19["count"] == 1201


def test_heatmap_max_count_consistent(client):
    body = client.get("/api/stats/heatmap").json()
    if body["cells"]:
        assert body["max_count"] >= max(c["count"] for c in body["cells"])


def test_heatmap_coverage_pct(client):
    body = client.get("/api/stats/heatmap").json()
    total = sum(c["count"] for c in body["cells"]) + sum(u["count"] for u in body["unmapped"])
    expected_pct = (sum(c["count"] for c in body["cells"]) / total * 100) if total else 0
    assert abs(body["coverage_pct"] - expected_pct) < 0.01


def test_heatmap_per_app_filter(client):
    body = client.get("/api/stats/heatmap?app=com.brave.Browser").json()
    # Browser session has just "right" → arrow
    keys = {c["key"] for c in body["cells"]}
    assert keys == set() or "→" in keys
