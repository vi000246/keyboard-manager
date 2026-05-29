"""Layout API integration tests.

Each test uses a fresh `TestClient` so the module reload picks up the
`VIAL_PATH` env var set per-test.
"""
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"


def _client(monkeypatch, vial_path, db_path=None):
    """Reload backend.main so module-level VIAL_PATH / DB_PATH picks up env."""
    monkeypatch.setenv("VIAL_PATH", str(vial_path))
    if db_path is not None:
        monkeypatch.setenv("DB_PATH", str(db_path))
    # Clear the layout cache between tests
    from backend.api import layout
    layout._cache.clear()
    from backend import main as backend_main
    importlib.reload(backend_main)
    return TestClient(backend_main.app)


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Layout tests don't touch stats, but main.py calls ensure_schema(DB_PATH)
    # at import time — point at tmp_path so it doesn't try /data/ on macOS.
    return _client(monkeypatch, FIXTURE, tmp_path / "t.db")


def test_layout_ok(client):
    r = client.get("/api/layout")
    assert r.status_code == 200
    body = r.json()
    assert len(body["layers"]) == 6
    first = body["layers"][0]["rows"][0]["keys"][0]
    assert first["raw"] == "KC_GRAVE"
    assert first["resolved"]["label_top"] == "`"


def test_layout_resolves_tap_dance_keys(client):
    body = client.get("/api/layout").json()
    # mylayout.vil layer 0 has TD(3) and TD(1) at known positions; find any TD(*) on layer 0
    td_keys = [
        k
        for row in body["layers"][0]["rows"]
        for k in row["keys"]
        if k is not None and k["raw"].startswith("TD(")
    ]
    assert td_keys, "expected at least one TD(*) in layer 0"
    for k in td_keys:
        r = k["resolved"]
        assert r["expanded_kind"] == "tap-dance"
        assert r["tap"] is not None
        assert isinstance(r["branches"], list) and len(r["branches"]) == 4


def test_layout_resolves_all_t_space(client):
    body = client.get("/api/layout").json()
    # mylayout.vil layer 0 row 4 col 4 = ALL_T(KC_SPACE)
    all_t = next(
        (k for row in body["layers"][0]["rows"]
         for k in row["keys"]
         if k is not None and k["raw"] == "ALL_T(KC_SPACE)"),
        None,
    )
    assert all_t is not None, "ALL_T(KC_SPACE) should be in layer 0"
    assert all_t["resolved"]["expanded_kind"] == "mod-tap"
    assert all_t["resolved"]["tap"] == "Space"
    assert all_t["resolved"]["hold"] == "Hyper"


def test_layout_resolves_lt1_tab(client):
    body = client.get("/api/layout").json()
    lt_keys = [
        k
        for row in body["layers"][0]["rows"]
        for k in row["keys"]
        if k is not None and k["raw"] == "LT1(KC_TAB)"
    ]
    assert lt_keys, "LT1(KC_TAB) should be in layer 0"
    r = lt_keys[0]["resolved"]
    assert r["expanded_kind"] == "layer-tap"
    assert r["label_top"] == "Tab"
    assert r["label_bottom"] == "→L1"


def test_layout_empty_slot_serializes_as_null(client):
    body = client.get("/api/layout").json()
    # mylayout.vil layer 0 row 0 col 6 is -1 (no inner col on num row)
    assert body["layers"][0]["rows"][0]["keys"][6] is None


def test_layout_keycodes_endpoint(client):
    r = client.get("/api/layout/keycodes")
    assert r.status_code == 200
    body = r.json()
    assert body["KC_GRAVE"] == "`"
    assert body["KC_SPACE"] == "Space"


def test_layout_503_when_vial_missing(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path / "absent.vil", tmp_path / "t.db")
    r = c.get("/api/layout")
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "VIAL_NOT_FOUND"


def test_layout_422_on_unsupported_protocol(monkeypatch, tmp_path):
    bad = tmp_path / "bad.vil"
    bad.write_text('{"vial_protocol": 99, "version": 1, "layout": []}')
    c = _client(monkeypatch, bad, tmp_path / "t.db")
    r = c.get("/api/layout")
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "VIAL_PARSE_ERROR"


def test_health_endpoint_reports_vial_exists(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["vial_exists"] is True


def test_macro_field_present_and_empty(client):
    """mylayout.vil ships empty macro slots — the API surfaces an empty list,
    not the 15 unset slots (those carry zero info and would clutter UI lookups)."""
    body = client.get("/api/layout").json()
    assert body["macro"] == []


def test_macro_field_with_actions(monkeypatch, tmp_path):
    """When .vil has macro actions, the API exposes index + raw + actions
    so the frontend can attach a 'macro N' badge to MACRO{N} cells and
    show the action list in the hover tooltip."""
    import json
    src = json.loads(FIXTURE.read_text())
    # Drop a macro into slot 0 and slot 2 (slot 1 stays empty to verify
    # filtering of unset entries).
    src["macro"] = [
        [["tap", "KC_H"], ["tap", "KC_I"]],
        [],
        [["text", "hello"]],
    ]
    p = tmp_path / "with_macros.vil"
    p.write_text(json.dumps(src))
    c = _client(monkeypatch, p, tmp_path / "t.db")
    body = c.get("/api/layout").json()
    assert len(body["macro"]) == 2
    by_idx = {m["index"]: m for m in body["macro"]}
    assert by_idx[0]["raw"] == "MACRO0"
    assert by_idx[0]["actions"] == [["tap", "KC_H"], ["tap", "KC_I"]]
    assert by_idx[2]["raw"] == "MACRO2"


def test_macro_resolved_kind(monkeypatch, tmp_path):
    """A MACRO0 cell in a layer should resolve to expanded_kind='macro' with
    a human label, so the renderer can pick it up regardless of whether the
    macro is defined yet."""
    import json
    src = json.loads(FIXTURE.read_text())
    # Stick MACRO0 somewhere harmless on layer 0: replace KC_GRAVE (row 0 col 0)
    src["layout"][0][0][0] = "MACRO0"
    p = tmp_path / "macro_cell.vil"
    p.write_text(json.dumps(src))
    c = _client(monkeypatch, p, tmp_path / "t.db")
    body = c.get("/api/layout").json()
    cell = body["layers"][0]["rows"][0]["keys"][0]
    assert cell["raw"] == "MACRO0"
    assert cell["resolved"]["expanded_kind"] == "macro"
    assert cell["resolved"]["label_top"] == "macro 0"


def test_combo_includes_resolved_labels(client):
    """Combo serialization adds trigger_labels + output_label so the frontend
    tooltip can show 'J + K → Esc' without re-doing keycode resolution."""
    body = client.get("/api/layout").json()
    # mylayout.vil combo[0] = ["KC_J", "KC_K", "KC_NO", "KC_NO", "KC_ESCAPE"]
    c0 = body["combo"][0]
    assert c0["triggers"] == ["KC_J", "KC_K"]
    assert c0["trigger_labels"] == ["J", "K"]
    assert c0["output"] == "KC_ESCAPE"
    assert c0["output_label"] == "Esc"


def test_mylayout_full_keycode_coverage(client):
    """M1 acceptance gate (task 1.5).

    Every non-empty, non-transparent key in mylayout.vil must have a
    non-empty label_top. Fall-throughs to expanded_kind='unknown' are
    permitted only if label_top is non-empty (e.g. an unrecognised but
    still printable token); a None label_top fails the gate.
    """
    body = client.get("/api/layout").json()
    missing: list[tuple[int, int, int, str]] = []
    for layer in body["layers"]:
        for row in layer["rows"]:
            for col, k in enumerate(row["keys"]):
                if k is None:
                    continue
                r = k["resolved"]
                if r["expanded_kind"] in ("transparent", "empty"):
                    continue
                if not r["label_top"]:
                    missing.append((layer["index"], row["row"], col, k["raw"]))
    assert not missing, (
        f"missing label_top for {len(missing)} keys; first 20: {missing[:20]}"
    )
