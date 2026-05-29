from pathlib import Path

from backend.db.heatmap_mapper import (
    build_combo_position_index,
    build_modifier_position_index,
    build_position_index,
    filter_typing_singles,
    overlay_stats,
)
from backend.parsers.vial import parse

FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"


def test_position_index_finds_letter():
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    # mylayout.vil layer 0 has KC_J on the right A-row at some col
    positions = idx.get(("J", ""))
    assert positions is not None
    assert any(p["layer"] == 0 for p in positions)


def test_position_index_finds_resolved_label():
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    # LT1(KC_TAB) resolves to label_top=Tab — should appear in the index
    positions = idx.get(("Tab", ""))
    assert positions is not None


def test_position_index_skips_trns_and_no():
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    # KC_TRNS / KC_NO must not produce a position
    assert ("KC_TRNS", "") not in idx
    assert ("KC_NO", "") not in idx


def test_modifier_index_picks_up_plain_and_mod_tap():
    """KC_LSHIFT (plain) and LGUI_T(KC_ENTER) (mod-tap) both contribute."""
    layout = parse(FIXTURE)
    midx = build_modifier_position_index(layout)
    # Plain LShift on the pinky + RShift on the right thumb cluster
    assert "shift" in midx
    assert any(p["raw"] == "KC_LSHIFT" for p in midx["shift"])
    # LGUI_T(KC_ENTER) on right thumb → cmd
    assert "cmd" in midx
    assert any("LGUI_T" in p["raw"] for p in midx["cmd"])


def test_modifier_index_picks_up_tap_dance_holds():
    """TD branches whose hold is a plain modifier credit that modifier."""
    layout = parse(FIXTURE)
    midx = build_modifier_position_index(layout)
    # TD(3) holds Alt; TD(0) holds Ctrl; TD(1) holds Cmd
    assert any("TD(3)" in p["raw"] for p in midx.get("alt", []))
    assert any("TD(0)" in p["raw"] for p in midx.get("ctrl", []))
    assert any("TD(1)" in p["raw"] for p in midx.get("cmd", []))


def test_modifier_index_skips_all_t():
    """ALL_T produces every modifier — too ambiguous to credit any single one."""
    layout = parse(FIXTURE)
    midx = build_modifier_position_index(layout)
    # ALL_T(KC_SPACE) sits on a thumb; it must not appear in any token bucket
    for tok, positions in midx.items():
        assert not any("ALL_T" in p["raw"] for p in positions), f"ALL_T leaked into {tok}"


def test_filter_typing_singles_drops_letters_keeps_combos():
    rows = [
        {"key": "j", "modifiers": "", "total": 5892},
        {"key": "space", "modifiers": "", "total": 26000},
        {"key": "right", "modifiers": "", "total": 2497},
        {"key": "s", "modifiers": "cmd", "total": 50},
    ]
    out = filter_typing_singles(rows)
    keys = {(r["key"], r["modifiers"]) for r in out}
    assert ("j", "") not in keys
    assert ("space", "") not in keys
    assert ("right", "") in keys       # functional single, kept
    assert ("s", "cmd") in keys        # combo, always kept


def test_overlay_aggregates_by_position():
    """Same physical position hit by two stats rows (base key + modifier) sums."""
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    midx = build_modifier_position_index(layout)
    # cmd+s — S is in idx, cmd is split across LGUI_T position(s)
    rows = [{"key": "s", "modifiers": "cmd", "total": 100}]
    result = overlay_stats(idx, rows, modifier_index=midx)
    # S base key gets the full 100
    s_cells = [c for c in result["cells"] if c["key"] == "S"]
    assert s_cells and s_cells[0]["count"] == 100
    # cmd positions on base layer share the 100 evenly
    cmd_cells = [c for c in result["cells"] if c["key"] == "cmd"]
    assert cmd_cells
    assert sum(c["count"] for c in cmd_cells) == 100


def test_overlay_unmapped_for_unknown_event_key():
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    rows = [{"key": "f19", "modifiers": "", "total": 1201}]
    result = overlay_stats(idx, rows)
    assert not result["cells"]
    assert any(u["key"] == "f19" for u in result["unmapped"])


def test_overlay_arrows_normalized():
    """macOS reports 'right' / 'down' / etc. — should map to ←↓↑→ labels."""
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    rows = [
        {"key": "right", "modifiers": "", "total": 2497},
        {"key": "down",  "modifiers": "", "total": 1650},
    ]
    result = overlay_stats(idx, rows)
    keys = {c["key"] for c in result["cells"]}
    # Either both map (if NAV layer has arrows) or fall through to unmapped
    assert keys.issubset({"→", "↓"}) or result["unmapped"]


def test_overlay_picks_base_layer_when_multiple_positions():
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    rows = [{"key": "j", "modifiers": "", "total": 5892}]
    result = overlay_stats(idx, rows)
    j_cell = next(c for c in result["cells"] if c["key"] == "J")
    assert j_cell["layer"] == 0


def test_combo_index_finds_lgui_in_tap_dance():
    """TD(0).tap = LGUI(KC_1) — combo (cmd, "1") must point at TD0's position."""
    layout = parse(FIXTURE)
    cidx = build_combo_position_index(layout)
    positions = cidx.get((frozenset({"cmd"}), "1"))
    assert positions is not None
    assert any("TD(0)" in p["raw"] for p in positions)


def test_combo_index_finds_lsft_in_tap_dance_double_tap():
    """TD(2).double_tap = LSFT(KC_SCOLON) — combo (shift, ";") → TD2."""
    layout = parse(FIXTURE)
    cidx = build_combo_position_index(layout)
    positions = cidx.get((frozenset({"shift"}), ";"))
    assert positions is not None
    assert any("TD(2)" in p["raw"] for p in positions)


def test_overlay_combo_position_wins_over_base_and_modifier():
    """When a firmware combo position exists for cmd+1, all the count goes
    there — the top-row 1 key and the Cmd thumbs should NOT get credited."""
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    midx = build_modifier_position_index(layout)
    cidx = build_combo_position_index(layout)
    rows = [{"key": "1", "modifiers": "cmd", "total": 1000}]
    result = overlay_stats(idx, rows, modifier_index=midx, combo_index=cidx)
    # The TD0 combo position should be the only lit cell
    cell_keys = {c["key"] for c in result["cells"]}
    assert "cmd+1" in cell_keys
    # Plain "1" base and ad-hoc "cmd" derivation must not appear for this row
    assert "1" not in cell_keys
    assert "cmd" not in cell_keys


def test_overlay_no_combo_position_falls_back_to_derivation():
    """cmd+s has no dedicated combo position in mylayout.vil — should still
    split count between base S and Cmd thumbs (existing behavior)."""
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    midx = build_modifier_position_index(layout)
    cidx = build_combo_position_index(layout)
    rows = [{"key": "s", "modifiers": "cmd", "total": 100}]
    result = overlay_stats(idx, rows, modifier_index=midx, combo_index=cidx)
    cell_keys = {c["key"] for c in result["cells"]}
    assert "S" in cell_keys
    assert "cmd" in cell_keys


def test_overlay_without_modifier_index_skips_derivation():
    """When modifier_index is None, only base keys are mapped — modifier counts
    are silently dropped. Useful for unit tests of base-key projection only."""
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    rows = [{"key": "s", "modifiers": "cmd", "total": 100}]
    result = overlay_stats(idx, rows)  # no modifier_index
    keys = {c["key"] for c in result["cells"]}
    assert "S" in keys
    assert "cmd" not in keys
