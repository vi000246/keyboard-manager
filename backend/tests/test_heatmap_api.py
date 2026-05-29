import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db.migrations import ensure_schema
from backend.tests.conftest import seed_events

FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    ensure_schema(db)
    # Mix of typing singles (filtered), functional singles (kept), combos (kept).
    seed_events(db, {
        "com.googlecode.iterm2": {
            "j": 5892,            # letter — filtered
            "k": 2314,            # letter — filtered
            "f19": 1201,          # unmapped functional single — kept, ends up in unmapped
            "cmd+s": 50,          # combo — kept, S + cmd both lit
            "cmd+shift+t": 20,    # combo — T + cmd + shift all lit
        },
        "com.brave.Browser": {
            "right": 2497,        # arrow — kept (functional single)
            "cmd+t": 30,          # combo — kept
        },
    })
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


def test_heatmap_filters_out_letter_singles(client):
    """J and K are pure typing — must not appear in the heatmap."""
    body = client.get("/api/stats/heatmap").json()
    cell_keys = {c["key"] for c in body["cells"]}
    assert "J" not in cell_keys
    assert "K" not in cell_keys


def test_heatmap_keeps_combos_and_derives_modifier(client):
    """cmd+s should light up both S (base) and the cmd-producing position(s)."""
    body = client.get("/api/stats/heatmap").json()
    cell_keys = {c["key"] for c in body["cells"]}
    # S appears because of cmd+s (count=50)
    assert "S" in cell_keys
    # cmd derivation surfaces a "cmd" cell
    assert "cmd" in cell_keys


def test_heatmap_f19_unmapped(client):
    body = client.get("/api/stats/heatmap").json()
    f19 = next((u for u in body["unmapped"] if u["key"] == "f19"), None)
    assert f19 is not None
    assert f19["count"] == 1201


def test_heatmap_max_count_consistent(client):
    body = client.get("/api/stats/heatmap").json()
    if body["cells"]:
        assert body["max_count"] >= max(c["count"] for c in body["cells"])


def test_heatmap_per_app_filter(client):
    body = client.get("/api/stats/heatmap?app=com.brave.Browser").json()
    cell_keys = {c["key"] for c in body["cells"]}
    # Browser has 'right' (arrow) + cmd+t — T + cmd should be lit, J/K from
    # iterm2 must not leak across the filter.
    assert "J" not in cell_keys
    # At least one of the expected keys should be present
    assert cell_keys & {"→", "T", "cmd"}
