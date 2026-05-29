"""Map keystat event-keys to physical (layer, row, col) positions.

The macOS event layer reports keys after firmware translation, so a press of
the LT1(KC_TAB) thumb shows up as "tab". We index the resolved label of every
non-transparent slot in the layout, then look event keys up against that index.

The heatmap intentionally excludes plain-typing events (letters, digits, space,
enter, punctuation, backspace). Those dominate during normal typing and bury
the shortcut/hotkey signal the heatmap exists to surface. Combo events
(`modifiers != ''`) are always included; their modifier portion is also
attributed to the physical modifier key(s) on the layout so the thumb cluster
lights up when it's doing real work.

Keys without a physical home (e.g. f19 produced by Karabiner, or anything not
in mylayout.vil) end up in `unmapped[]` rather than being silently dropped.
"""
from __future__ import annotations

from collections import defaultdict

from ..parsers.keycodes import LayoutContext, _strip_wrapper, resolve
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

# Event-key labels (post-normalization) that count as "typing volume" and are
# excluded from the heatmap when they appear without modifiers. The point of
# the heatmap is to surface shortcut/hotkey usage; raw typing on these keys
# would swamp every other signal.
TYPING_SINGLE_LABELS: frozenset[str] = frozenset(
    list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    + list("0123456789")
    + ["Space", "Enter", "Bksp", "Del",
       ".", ",", ";", "'", '"', "/", "\\", "-", "=", "[", "]", "`", "~"]
)

# events.modifiers token → physical key labels produced by parsers/keycodes.py.
# Both L/R variants are listed; positions for whichever exist on the user's
# layout will share the modifier's count.
_MOD_LABEL_TO_TOKEN: dict[str, str] = {
    "Cmd":    "cmd",  "RCmd":   "cmd",
    "Shift":  "shift", "LShift": "shift", "RShift": "shift",
    "Ctrl":   "ctrl", "RCtrl":  "ctrl",
    "Alt":    "alt",  "RAlt":   "alt",
}

# QMK mod-wrapper prefix → events.modifiers token. Drives combo-position
# extraction so `LGUI(KC_1)` → ("cmd", "1") and nested wrappers like
# `LCTL(LSFT(KC_X))` accumulate to {"ctrl", "shift"}.
_WRAPPER_TO_TOKEN: dict[str, str] = {
    "LSFT": "shift", "RSFT": "shift",
    "LCTL": "ctrl",  "RCTL": "ctrl",
    "LALT": "alt",   "RALT": "alt",
    "LGUI": "cmd",   "RGUI": "cmd",
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


def _combo_from_keycode(
    raw: str, ctx: LayoutContext
) -> tuple[frozenset[str], str] | None:
    """If `raw` is one or more nested mod-wrappers around a plain key, return
    (modifier_set, base_label). Returns None for plain keys, mod-taps,
    layer-taps, and anything else.
    """
    mods: set[str] = set()
    cur = raw
    while True:
        matched = False
        for prefix, mod_token in _WRAPPER_TO_TOKEN.items():
            inner = _strip_wrapper(cur, prefix)
            if inner is not None:
                mods.add(mod_token)
                cur = inner
                matched = True
                break
        if not matched:
            break
    if not mods:
        return None
    base_label = resolve(cur, ctx).label_top
    if not base_label:
        return None
    return frozenset(mods), base_label


def build_combo_position_index(
    layout: Layout,
) -> dict[tuple[frozenset[str], str], list[dict]]:
    """Build (modifier_set, base_label) → [{layer, row, col, raw}, ...].

    Indexes physical positions that produce a *specific* mod+base combo via
    firmware — `LGUI(KC_1)` on a thumb, `LSFT(KC_SCOLON)` as a tap-dance
    double-tap, nested `LCTL(LSFT(KC_X))`, etc. Lets the heatmap attribute
    a `cmd+1` event to the actual thumb the user pressed instead of
    splitting the count between the top-row `1` key and the Cmd thumbs.
    """
    ctx = LayoutContext(tap_dance=list(layout.tap_dance))
    idx: dict[tuple[frozenset[str], str], list[dict]] = defaultdict(list)
    for layer in layout.layers:
        for row in layer.rows:
            for ci, raw in enumerate(row.keys):
                if raw is None or raw in ("KC_NO", "KC_TRNS"):
                    continue
                for combo in _extract_combos(raw, ctx):
                    idx[combo].append(
                        {"layer": layer.index, "row": row.row, "col": ci, "raw": raw}
                    )
    return dict(idx)


def _extract_combos(
    raw: str, ctx: LayoutContext
) -> list[tuple[frozenset[str], str]]:
    """Combos this raw keycode produces. Walks tap-dance branches so each
    branch (tap / hold / double_tap / tap_hold) can contribute its own combo.
    """
    direct = _combo_from_keycode(raw, ctx)
    if direct:
        return [direct]
    if raw.startswith("TD(") and raw.endswith(")"):
        idx_str = raw[3:-1]
        if idx_str.isdigit():
            td_idx = int(idx_str)
            td_list = ctx.tap_dance
            td = td_list[td_idx] if 0 <= td_idx < len(td_list) else None
            if td:
                out: list[tuple[frozenset[str], str]] = []
                for branch_raw in (td.tap, td.hold, td.double_tap, td.tap_hold):
                    if branch_raw and branch_raw not in ("KC_NO", "KC_TRNS"):
                        c = _combo_from_keycode(branch_raw, ctx)
                        if c:
                            out.append(c)
                return out
    return []


def build_modifier_position_index(layout: Layout) -> dict[str, list[dict]]:
    """Build modifier_token → [{layer, row, col, raw}, ...].

    `modifier_token` matches the values stored in events.modifiers
    (`cmd`/`shift`/`ctrl`/`alt`). A position is credited to a token when it
    unambiguously produces that single modifier — plain mod keys (KC_LSHIFT),
    mod-tap holds (LGUI_T → cmd on hold), or tap-dance branches whose hold is
    a plain modifier. Multi-mod sources like ALL_T are deliberately skipped:
    we can't tell which modifier the user was actually after, and crediting
    all four would dilute the signal.
    """
    ctx = LayoutContext(tap_dance=list(layout.tap_dance))
    idx: dict[str, list[dict]] = defaultdict(list)
    for layer in layout.layers:
        for row in layer.rows:
            for ci, raw in enumerate(row.keys):
                if raw is None or raw in ("KC_NO", "KC_TRNS"):
                    continue
                rk = resolve(raw, ctx)
                tok: str | None = None
                if rk.label_top in _MOD_LABEL_TO_TOKEN:
                    tok = _MOD_LABEL_TO_TOKEN[rk.label_top]
                elif rk.hold and rk.hold in _MOD_LABEL_TO_TOKEN:
                    tok = _MOD_LABEL_TO_TOKEN[rk.hold]
                if tok:
                    idx[tok].append(
                        {"layer": layer.index, "row": row.row, "col": ci, "raw": raw}
                    )
    return dict(idx)


def filter_typing_singles(stats_rows: list[dict]) -> list[dict]:
    """Drop single-key rows (modifiers == '') whose normalized label is a
    typing key. Combo rows pass through unchanged.
    """
    keep: list[dict] = []
    for row in stats_rows:
        if row.get("modifiers"):
            keep.append(row)
            continue
        if _normalize_event_key(row["key"]) in TYPING_SINGLE_LABELS:
            continue
        keep.append(row)
    return keep


def _pick_positions(positions: list[dict]) -> list[dict]:
    """When a key exists on multiple layers, attribute count to base layer
    only — otherwise a Cmd press would double-count itself on every layer
    where KC_TRNS makes it transparent (none in practice for plain mods, but
    keeps semantics consistent with build_position_index).
    """
    base = [p for p in positions if p["layer"] == 0]
    return base or positions


def overlay_stats(
    position_index: dict[tuple[str, str], list[dict]],
    stats_rows: list[dict],
    modifier_index: dict[str, list[dict]] | None = None,
    combo_index: dict[tuple[frozenset[str], str], list[dict]] | None = None,
) -> dict:
    """Project stats_rows onto physical positions.

    stats_rows: list of {"key", "modifiers", "total"} (StatsRepo.top_n shape).
    modifier_index: when provided, ad-hoc combo rows credit each modifier's
      physical key(s) (count split evenly across L/R if both exist).
    combo_index: when provided, combo rows that match a dedicated firmware
      shortcut position (e.g. `LGUI(KC_1)` on a thumb) get the full count
      attributed there and skip the base/modifier derivation — otherwise the
      thumb the user actually presses would never light up while the top-row
      `1` and Cmd thumbs falsely glow.

    Returns:
      {
        "cells":    [{layer, row, col, key, count}, ...]  aggregated by position
        "unmapped": [{key, modifiers, count, reason}, ...]
        "max_count": int  — for log-scale color domain in frontend
      }
    """
    cells_by_pos: dict[tuple[int, int, int], dict] = {}
    unmapped: list[dict] = []

    def _add(pos: dict, key_label: str, count: float) -> None:
        k = (pos["layer"], pos["row"], pos["col"])
        cell = cells_by_pos.get(k)
        if cell is None:
            cells_by_pos[k] = {
                "layer": pos["layer"], "row": pos["row"], "col": pos["col"],
                "key": key_label, "count": count,
            }
        else:
            cell["count"] += count

    for row in stats_rows:
        count = row["total"]
        mods_str = row.get("modifiers", "")
        normalized = _normalize_event_key(row["key"])

        # 1. Dedicated firmware combo wins when it exists — attribute the
        #    whole count there and skip base/modifier derivation. This is
        #    what makes Cmd+1 light up the TD0 thumb instead of the top-row 1.
        if mods_str and combo_index:
            mods_set = frozenset(t for t in mods_str.split("+") if t)
            combo_positions = combo_index.get((mods_set, normalized))
            if combo_positions:
                effective = _pick_positions(combo_positions)
                share = count / len(effective)
                label = f"{'+'.join(sorted(mods_set))}+{normalized}"
                for p in effective:
                    _add(p, label, share)
                continue

        # 2. Otherwise: project base key + derive modifier credits separately.
        positions = position_index.get((normalized, ""))
        if positions:
            pos = next((p for p in positions if p["layer"] == 0), positions[0])
            _add(pos, normalized, count)
        else:
            unmapped.append({
                "key": row["key"],
                "modifiers": mods_str,
                "count": count,
                "reason": "no physical position",
            })

        if not (mods_str and modifier_index):
            continue
        for tok in mods_str.split("+"):
            tok = tok.strip()
            mod_positions = modifier_index.get(tok)
            if not mod_positions:
                continue
            effective = _pick_positions(mod_positions)
            share = count / len(effective)
            for p in effective:
                _add(p, tok, share)

    cells = list(cells_by_pos.values())
    for c in cells:
        c["count"] = int(round(c["count"]))
    max_count = max((c["count"] for c in cells), default=0)
    return {"cells": cells, "unmapped": unmapped, "max_count": max_count}
