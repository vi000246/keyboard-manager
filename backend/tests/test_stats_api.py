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
                "com.googlecode.iterm2": {"j": 5892, "k": 2314, "cmd+v": 3},
                "com.brave.Browser": {"right": 2497, "cmd+1": 1529},
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


def test_apps_endpoint_lists_imported_bundles(client):
    r = client.get("/api/apps")
    assert r.status_code == 200
    bundles = {a["bundle_id"] for a in r.json()}
    assert {"com.googlecode.iterm2", "com.brave.Browser"} <= bundles


def test_apps_endpoint_includes_bucket(client):
    apps = client.get("/api/apps").json()
    iterm = next(a for a in apps if a["bundle_id"] == "com.googlecode.iterm2")
    assert iterm["bucket"] == "terminal"


def test_stats_top_n_per_app(client):
    r = client.get("/api/stats?app=com.googlecode.iterm2&top=5&kind=single")
    assert r.status_code == 200
    body = r.json()
    assert body["scope"]["app"] == "com.googlecode.iterm2"
    assert body["scope"]["kind"] == "single"
    assert body["total_events"] > 0
    assert body["rows"][0]["key"] == "j"
    assert body["rows"][0]["count"] == 5892


def test_stats_top_n_global(client):
    r = client.get("/api/stats?top=10")
    body = r.json()
    # Without app filter, totals are across all apps
    assert body["total_events"] >= 5892 + 2314 + 2497
    keys = {(row["key"], row["modifiers"]) for row in body["rows"]}
    assert ("j", "") in keys
    assert ("right", "") in keys


def test_stats_mod_kind(client):
    r = client.get("/api/stats?kind=mod&top=10")
    body = r.json()
    pairs = {(row["key"], row["modifiers"]) for row in body["rows"]}
    assert ("v", "cmd") in pairs or ("1", "cmd") in pairs


def test_stats_all_kind_includes_both(client):
    r = client.get("/api/stats?kind=all&top=20")
    body = r.json()
    pairs = {(row["key"], row["modifiers"]) for row in body["rows"]}
    assert ("j", "") in pairs
    assert ("v", "cmd") in pairs


def test_stats_pct_field(client):
    r = client.get("/api/stats?app=com.googlecode.iterm2&top=5&kind=single")
    body = r.json()
    assert all("pct" in row for row in body["rows"])
    # Top row 'j' (5892) over total iterm singles (5892+2314=8206)
    total = body["total_events"]
    j_row = next(r for r in body["rows"] if r["key"] == "j")
    assert abs(j_row["pct"] - (5892 / total * 100)) < 0.01


def test_stats_invalid_kind_rejected(client):
    r = client.get("/api/stats?kind=bogus")
    assert r.status_code == 422  # FastAPI Query regex validation
