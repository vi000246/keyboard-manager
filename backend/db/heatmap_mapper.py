"""Map keystat event-keys to physical (layer, row, col) positions.

The macOS event layer reports keys after firmware translation, so a press of
the LT1(KC_TAB) thumb shows up as "tab". We index the resolved label of every
non-transparent slot in the layout, then look event keys up against that index.

Keys without a physical home (e.g. f19 produced by Karabiner, or anything not
in mylayout.vil) end up in `unmapped[]` rather than being silently dropped.
"""
from __future__ import annotations

from collections import defaultdict

from ..parsers.keycodes import LayoutContext, resolve
from ..parsers.vial import Layout

# macOS event-key name → resolved label_top from keycode_labels
_EVENT_KEY_ALIASES: dict[str, str] = {
    "space": "Space",
    "return": "Enter",
    "delete": "Bksp",
    "forwarddelete": "Del",
    "escape": "Esc",
    "tab": "Tab",
    "capslock": "Caps",
    "caps_lock": "Caps",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
    "pageup": "PgUp",
    "pagedown": "PgDn",
    "home": "Home",
    "end": "End",
}


def _normalize_event_key(event_key: str) -> str:
    """Turn a macOS-event-layer key name into the resolved label form."""
    k = event_key.lower()
    if k in _EVENT_KEY_ALIASES:
        return _EVENT_KEY_ALIASES[k]
    if len(k) == 1:
        # Single character — uppercase to match KEYCODE_LABELS letter convention
        return k.upper()
    # Punctuation, function keys etc. fall through as-is; coverage gate will
    # surface anything that doesn't match a layout position.
    return k


def build_position_index(layout: Layout) -> dict[tuple[str, str], list[dict]]:
    """Build (label_top, modifiers="") → [{layer, row, col, raw}, ...].

    Modifiers are currently always '' because we map mod-combos like cmd+1 to
    the base key's position (the modifier itself lives on a different key).
    Multiple positions are possible for keys that appear on multiple layers.
    """
    ctx = LayoutContext(tap_dance=list(layout.tap_dance))
    idx: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for layer in layout.layers:
        for row in layer.rows:
            for ci, raw in enumerate(row.keys):
                if raw is None or raw in ("KC_NO", "KC_TRNS"):
                    continue
                rk = resolve(raw, ctx)
                if not rk.label_top:
                    continue
                idx[(rk.label_top, "")].append(
                    {"layer": layer.index, "row": row.row, "col": ci, "raw": raw}
                )
    return dict(idx)


def overlay_stats(
    position_index: dict[tuple[str, str], list[dict]],
    stats_rows: list[dict],
) -> dict:
    """Project stats_rows onto physical positions.

    stats_rows: list of {"key", "modifiers", "total"} (StatsRepo.top_n shape)

    Returns:
      {
        "cells": [{layer, row, col, key, count}, ...]  — mapped to base layer
                                                          when multiple match
        "unmapped": [{key, modifiers, count, reason}, ...]
        "max_count": int  — for log-scale color domain in frontend
      }
    """
    cells: list[dict] = []
    unmapped: list[dict] = []
    max_count = 0

    for row in stats_rows:
        normalized = _normalize_event_key(row["key"])
        positions = position_index.get((normalized, ""))
        if positions:
            # Prefer base layer (index 0); fall back to whatever's first.
            pos = next((p for p in positions if p["layer"] == 0), positions[0])
            count = row["total"]
            cells.append({
                "layer": pos["layer"],
                "row": pos["row"],
                "col": pos["col"],
                "key": normalized,
                "count": count,
            })
            max_count = max(max_count, count)
        else:
            unmapped.append({
                "key": row["key"],
                "modifiers": row.get("modifiers", ""),
                "count": row["total"],
                "reason": "no physical position",
            })

    return {"cells": cells, "unmapped": unmapped, "max_count": max_count}
