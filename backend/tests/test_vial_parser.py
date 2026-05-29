from pathlib import Path

import pytest

from backend.parsers.vial import VialParseError, parse

FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"


def test_parse_returns_layout_with_6_layers():
    layout = parse(FIXTURE)
    assert len(layout.layers) == 6


def test_parse_tap_dance_count():
    layout = parse(FIXTURE)
    assert len(layout.tap_dance) == 16


def test_parse_combo_count():
    layout = parse(FIXTURE)
    assert len(layout.combo) == 16


def test_parse_layer_0_first_key_raw():
    layout = parse(FIXTURE)
    assert layout.layers[0].rows[0].keys[0] == "KC_GRAVE"


def test_parse_layer_0_empty_slot_is_none():
    # Row 0 col 6 is -1 in mylayout.vil
    layout = parse(FIXTURE)
    assert layout.layers[0].rows[0].keys[6] is None


def test_parse_rejects_unsupported_protocol(tmp_path):
    bad = tmp_path / "bad.vil"
    bad.write_text('{"vial_protocol": 99, "version": 1, "layout": []}')
    with pytest.raises(VialParseError):
        parse(bad)


def test_parse_rejects_invalid_json(tmp_path):
    bad = tmp_path / "bad.vil"
    bad.write_text("{not valid json")
    with pytest.raises(VialParseError):
        parse(bad)


def test_parse_tap_dance_index_0_content():
    """mylayout.vil tap_dance[0] = ["LGUI(KC_1)", "KC_LCTRL", "KC_NO", "KC_NO", 200]"""
    layout = parse(FIXTURE)
    td0 = layout.tap_dance[0]
    assert td0.index == 0
    assert td0.tap == "LGUI(KC_1)"
    assert td0.hold == "KC_LCTRL"
    assert td0.tap_term_ms == 200


def test_parse_combo_index_0_jk_to_esc():
    """mylayout.vil combo[0] = ["KC_J", "KC_K", "KC_NO", "KC_NO", "KC_ESCAPE"]"""
    layout = parse(FIXTURE)
    c0 = layout.combo[0]
    assert c0.index == 0
    assert c0.triggers == ["KC_J", "KC_K"]
    assert c0.output == "KC_ESCAPE"


def test_parse_macros_array_preserved_when_empty():
    """mylayout.vil has 15 empty macro slots — they must still parse, not crash."""
    layout = parse(FIXTURE)
    assert len(layout.macros) == 15
    assert all(m.actions == [] for m in layout.macros)
    assert layout.macros[0].index == 0


def test_parse_macro_with_actions(tmp_path):
    """A populated macro array should preserve action sequences verbatim."""
    import json
    src = json.loads(FIXTURE.read_text())
    src["macro"] = [
        [["tap", "KC_H"], ["tap", "KC_I"]],
        [["text", "hello"]],
        [],
    ]
    p = tmp_path / "with_macros.vil"
    p.write_text(json.dumps(src))
    layout = parse(p)
    assert layout.macros[0].actions == [["tap", "KC_H"], ["tap", "KC_I"]]
    assert layout.macros[1].actions == [["text", "hello"]]
    assert layout.macros[2].actions == []
