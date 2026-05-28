from backend.parsers.keycodes import LayoutContext, resolve
from backend.parsers.vial import TapDance


def _ctx(tap_dance=None):
    return LayoutContext(tap_dance=tap_dance or [])


def test_plain_letter():
    r = resolve("KC_A", _ctx())
    assert r.expanded_kind == "plain"
    assert r.label_top == "A"
    assert r.label_bottom is None


def test_grave_accent():
    r = resolve("KC_GRAVE", _ctx())
    assert r.label_top == "`"


def test_kc_no_empty():
    r = resolve("KC_NO", _ctx())
    assert r.expanded_kind == "empty"
    assert r.label_top is None


def test_kc_trns_transparent():
    r = resolve("KC_TRNS", _ctx())
    assert r.expanded_kind == "transparent"
    assert r.label_top is None


def test_layer_tap():
    r = resolve("LT1(KC_TAB)", _ctx())
    assert r.expanded_kind == "layer-tap"
    assert r.label_top == "Tab"
    assert r.label_bottom == "→L1"
    assert r.tap == "Tab"
    assert r.hold == "→L1"


def test_layer_tap_double_digit():
    r = resolve("LT10(KC_SPACE)", _ctx())
    assert r.expanded_kind == "layer-tap"
    assert r.label_bottom == "→L10"


def test_mod_tap_all_t():
    r = resolve("ALL_T(KC_SPACE)", _ctx())
    assert r.expanded_kind == "mod-tap"
    assert r.label_top == "Space"
    assert r.label_bottom == "Hyper"
    assert r.tap == "Space"
    assert r.hold == "Hyper"


def test_lgui_t_enter():
    r = resolve("LGUI_T(KC_ENTER)", _ctx())
    assert r.expanded_kind == "mod-tap"
    assert r.tap == "Enter"
    assert r.hold == "Cmd"


def test_shift_wrapped_known_pair():
    r = resolve("LSFT(KC_SCOLON)", _ctx())
    assert r.expanded_kind == "shift-wrapped"
    assert r.label_top == ":"


def test_shift_wrapped_unknown_falls_back_to_arrow():
    r = resolve("LSFT(KC_A)", _ctx())
    assert r.label_top == "⇧A"


def test_lgui_wrapped_letter():
    """LGUI(KC_1) appears in tap_dance branches — used to produce 'Cmd+1' label."""
    r = resolve("LGUI(KC_1)", _ctx())
    assert r.expanded_kind == "mod-wrapped"
    assert r.label_top == "Cmd+1"


def test_tap_dance_branches():
    td0 = TapDance(
        index=0, tap="LGUI(KC_1)", hold="KC_LCTRL",
        double_tap="KC_NO", tap_hold="KC_NO", tap_term_ms=200,
    )
    r = resolve("TD(0)", _ctx(tap_dance=[td0]))
    assert r.expanded_kind == "tap-dance"
    assert r.tap == "Cmd+1"
    assert r.hold == "Ctrl"
    assert r.double_tap is None
    assert r.tap_hold is None
    assert r.tap_term_ms == 200
    assert len(r.branches) == 4
    assert r.branches[0] == {"action": "tap", "label": "Cmd+1"}


def test_tap_dance_label_bottom_carries_index():
    td0 = TapDance(
        index=3, tap="KC_TAB", hold="KC_LALT",
        double_tap="KC_NO", tap_hold="KC_NO", tap_term_ms=200,
    )
    r = resolve("TD(3)", _ctx(tap_dance=[None, None, None, td0]))
    assert r.label_top == "Tab"
    assert r.label_bottom == "TD3"


def test_unknown_keycode_falls_back_to_raw():
    r = resolve("KC_TOTALLY_MADE_UP", _ctx())
    assert r.expanded_kind == "unknown"
    assert r.label_top == "KC_TOTALLY_MADE_UP"
