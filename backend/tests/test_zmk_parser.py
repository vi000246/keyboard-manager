"""Tests for the ZMK keymap-JSON parser (backend/parsers/zmk.py).

The binding-conversion logic is exhaustively unit-tested (it's the part that
must be correct regardless of physical layout). A couple of integration tests
then exercise the full file → Layout path and the Vial/ZMK auto-detection.
"""
from __future__ import annotations

import json

import pytest

from backend.parsers import zmk
from backend.parsers.vial import VialParseError
from backend.parsers.zmk import DEFAULT_SLOT_MAP, convert_binding, looks_like_zmk


@pytest.mark.parametrize(
    "binding,expected",
    [
        ("&kp Q", "KC_Q"),
        ("&kp A", "KC_A"),
        ("&kp N1", "KC_1"),
        ("&kp N0", "KC_0"),
        ("&kp NUMBER_5", "KC_5"),
        ("&kp F11", "KC_F11"),
        ("&kp SPACE", "KC_SPACE"),
        ("&kp RET", "KC_ENTER"),
        ("&kp BSPC", "KC_BSPACE"),
        ("&kp EXCL", "LSFT(KC_1)"),       # shifted glyph
        ("&kp LG(C)", "LGUI(KC_C)"),      # modifier function
        ("&kp LC(LS(TAB))", "LCTL(LSFT(KC_TAB))"),  # nested
        ("&mt LCTRL A", "LCTL_T(KC_A)"),
        ("&mt LSHFT SPACE", "LSFT_T(KC_SPACE)"),
        ("&lt 2 SPACE", "LT2(KC_SPACE)"),
        ("&mo 1", "MO(1)"),
        ("&to 0", "TO(0)"),
        ("&tog 3", "TG(3)"),
        ("&trans", "KC_TRNS"),
        ("&none", "KC_NO"),
        ("&kp", "KC_NO"),                 # bare behavior, no param
        ("Q", "KC_Q"),                    # leading &kp dropped
    ],
)
def test_convert_binding(binding, expected):
    assert convert_binding(binding) == expected


def test_convert_binding_unknown_behavior_is_readable():
    # Bluetooth / RGB / bootloader etc. aren't translated — surfaced as text.
    assert convert_binding("&bt BT_SEL 0") == "bt BT_SEL 0"
    assert convert_binding("&sys_reset") == "sys_reset"


def _layer(bindings, name="L"):
    """Pad a binding list to the full slot map with &trans so no warning fires."""
    padded = list(bindings) + ["&trans"] * (len(DEFAULT_SLOT_MAP) - len(bindings))
    return {"name": name, "bindings": padded}


def _write(tmp_path, data):
    p = tmp_path / "keymap.json"
    p.write_text(json.dumps(data))
    return p


def test_parse_basic_layers(tmp_path):
    data = {
        "keyboard": "corne",
        "layers": [
            _layer(["&mt LCTRL ESC", "&kp Q", "&kp W", "&kp LG(C)"], "Base"),
            _layer(["&trans", "&kp N1", "&mo 2"], "Sym"),
        ],
    }
    layout = zmk.parse(_write(tmp_path, data))

    assert len(layout.layers) == 2
    # Flat bindings drop onto the grid in DEFAULT_SLOT_MAP order.
    r0 = layout.layers[0].rows[0].keys
    assert r0[0] == "LCTL_T(KC_ESCAPE)"
    assert r0[1] == "KC_Q"
    assert r0[2] == "KC_W"
    assert r0[3] == "LGUI(KC_C)"
    # Positions with no physical key stay None (e.g. row 0 col 6).
    assert r0[6] is None


def test_parse_keymap_editor_object_bindings(tmp_path):
    """keymap-editor stores bindings as {value, params} objects, not strings."""
    data = {
        "layers": [
            {
                "name": "Base",
                "bindings": [
                    {"value": "&kp", "params": [{"value": "Q"}]},
                    {"value": "&lt", "params": [{"value": "2"}, {"value": "SPACE"}]},
                    {"value": "&kp", "params": [{"value": "LG", "params": [{"value": "C"}]}]},
                ],
            }
        ]
    }
    layout = zmk.parse(_write(tmp_path, data))
    r0 = layout.layers[0].rows[0].keys
    assert r0[0] == "KC_Q"
    assert r0[1] == "LT2(KC_SPACE)"
    assert r0[2] == "LGUI(KC_C)"


def test_parse_combos_map_positions_to_base_keycodes(tmp_path):
    data = {
        "layers": [_layer(["&kp Q", "&kp W", "&kp E"], "Base")],
        "combos": [
            {"name": "qw_esc", "keyPositions": [0, 1], "bindings": ["&kp ESC"]},
        ],
    }
    layout = zmk.parse(_write(tmp_path, data))
    assert len(layout.combo) == 1
    combo = layout.combo[0]
    assert combo.triggers == ["KC_Q", "KC_W"]   # positions → base keycodes
    assert combo.output == "KC_ESCAPE"


def test_parse_rejects_missing_layers(tmp_path):
    with pytest.raises(VialParseError):
        zmk.parse(_write(tmp_path, {"keyboard": "corne"}))


def test_parse_rejects_bad_json(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json")
    with pytest.raises(VialParseError):
        zmk.parse(p)


def test_looks_like_zmk_discriminates_from_vial():
    assert looks_like_zmk({"layers": [], "keyboard": "x"}) is True
    # A Vial file has vial_protocol — must NOT be treated as ZMK.
    assert looks_like_zmk({"vial_protocol": 6, "layout": []}) is False
    assert looks_like_zmk({"foo": 1}) is False
