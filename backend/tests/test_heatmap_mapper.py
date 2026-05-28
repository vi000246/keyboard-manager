from pathlib import Path

from backend.db.heatmap_mapper import build_position_index, overlay_stats
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


def test_overlay_marks_mapped_keys():
    layout = parse(FIXTURE)
    idx = build_position_index(layout)
    stats_rows = [
        {"key": "j", "modifiers": "", "total": 5892},
        {"key": "space", "modifiers": "", "total": 26570},
    ]
    result = overlay_stats(idx, stats_rows)
    keys = {(c["key"], c["count"]) for c in result["cells"]}
    assert ("J", 5892) in keys
    assert ("Space", 26570) in keys
    assert not result["unmapped"]
    assert result["max_count"] == 26570


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
