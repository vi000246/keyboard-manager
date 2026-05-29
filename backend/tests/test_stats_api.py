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
    seed_events(db, {
        "com.googlecode.iterm2": {"j": 5892, "k": 2314, "cmd+v": 3},
        "com.brave.Browser": {"right": 2497, "cmd+1": 1529},
    })
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


def test_apps_endpoint_includes_display_name(client):
    apps = client.get("/api/apps").json()
    iterm = next(a for a in apps if a["bundle_id"] == "com.googlecode.iterm2")
    assert iterm["display_name"] == "iTerm"
    brave = next(a for a in apps if a["bundle_id"] == "com.brave.Browser")
    assert brave["display_name"] == "Brave"


def test_apps_endpoint_includes_total_count(client):
    apps = client.get("/api/apps").json()
    iterm = next(a for a in apps if a["bundle_id"] == "com.googlecode.iterm2")
    # Fixture iterm: j=5892, k=2314, cmd+v=3 → 8209 total events
    assert iterm["total_count"] == 5892 + 2314 + 3


def test_apps_endpoint_sorted_by_total_count_desc(client):
    counts = [a["total_count"] for a in client.get("/api/apps").json()]
    assert counts == sorted(counts, reverse=True)


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


def test_stats_key_filter_modifiers_substring(client):
    """key=cmd should return rows whose modifiers contain 'cmd' (case-insensitive)."""
    r = client.get("/api/stats?kind=all&key=cmd")
    body = r.json()
    pairs = {(row["key"], row["modifiers"]) for row in body["rows"]}
    # iTerm: cmd+v=3, Brave: cmd+1=1529 — both should appear
    assert ("v", "cmd") in pairs
    assert ("1", "cmd") in pairs
    # Plain keys (no mods) must NOT match a "cmd" modifier filter
    assert ("j", "") not in pairs
    assert ("right", "") not in pairs


def test_stats_key_filter_returns_long_tail(tmp_path, monkeypatch):
    """key filter must surface rare combos even past the default top=50 cap."""
    db = tmp_path / "t.db"
    ensure_schema(db)
    # Seed 60 distinct Cmd combos with counts 1..60 + a giant non-cmd row.
    # Without key filter, only the top 50 would surface (and Cmd combos with
    # count <= 10 would be excluded). With key=cmd, all 60 must appear.
    cmd_events = {f"cmd+{c}": i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_-+={}[];'\",.<>?/`~|\\", start=1)}
    cmd_events = dict(list(cmd_events.items())[:60])
    seed_events(db, {"com.test.app": {**cmd_events, "j": 99999}})
    monkeypatch.setenv("VIAL_PATH", str(FIXTURE))
    monkeypatch.setenv("DB_PATH", str(db))
    from backend.api import layout as layout_mod
    layout_mod._cache.clear()
    from backend import main as backend_main
    importlib.reload(backend_main)
    c = TestClient(backend_main.app)

    body = c.get("/api/stats?kind=all&key=cmd").json()
    cmd_rows = [r for r in body["rows"] if "cmd" in r["modifiers"]]
    assert len(cmd_rows) == 60
    # Rare ones (count=1, 2) must be in the result
    counts = {r["count"] for r in cmd_rows}
    assert 1 in counts and 2 in counts


def test_stats_key_filter_pct_relative_to_filtered_scope(client):
    """With key=cmd, pct must be share of cmd events, not of all events."""
    body = client.get("/api/stats?kind=all&key=cmd").json()
    # total_events should equal the sum of cmd-modifier events only
    # (iTerm cmd+v=3 + Brave cmd+1=1529 = 1532)
    assert body["total_events"] == 1532
    # And the row pct should sum to ~100%
    pct_sum = sum(r["pct"] for r in body["rows"])
    assert abs(pct_sum - 100.0) < 0.01


def test_stats_key_filter_echoed_in_scope(client):
    """scope.key should echo the filter so the frontend can verify."""
    body = client.get("/api/stats?key=cmd").json()
    assert body["scope"]["key"] == "cmd"
    no_key = client.get("/api/stats").json()
    assert no_key["scope"]["key"] is None
