"""ZMK keymap-JSON loader.

ZMK Studio has no official keymap export format yet (zmk-studio issue #124),
so the realistic file a user will have is a *keymap-JSON* export — the shape
produced by the community keymap-editor and similar tools. This parser targets
that shape and is deliberately tolerant of the small variations seen in the
wild.

The strategy is **convert, don't re-implement**: every ZMK binding is rewritten
into the QMK-style keycode string the existing Vial pipeline already expands
(`&kp Q` → `KC_Q`, `&lt 2 SPACE` → `LT2(KC_SPACE)`, `&mt LCTRL A` →
`LCTL_T(KC_A)`, `&trans` → `KC_TRNS`). The result is a `vial.Layout`, so
`api/layout._load`, the keycode resolver, and the whole frontend work unchanged.

═══════════════════════════════════════════════════════════════════════════════
⚠️  UNTESTED AGAINST REAL HARDWARE — adjust when you get a ZMK board.
═══════════════════════════════════════════════════════════════════════════════

Two assumptions you will likely need to revisit once you have a real export:

1. **Schema** — see `_extract_layers()` for every accepted shape. If your export
   differs, widen it there.
2. **Physical layout** — ZMK bindings are a flat list per layer (in key-position
   order). The frontend renders a fixed 10-row × 7-column split grid, so we drop
   the flat list onto `DEFAULT_SLOT_MAP` (the live-key positions of the bundled
   sample board) in order. If your ZMK board has a different physical shape,
   redefine `DEFAULT_SLOT_MAP` to match it.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .vial import Combo, Layer, Layout, Row, VialParseError
from .zmk_keycodes import ZMK_MOD_TO_MOD_TAP, ZMK_MODFN, ZMK_TO_QMK

logger = logging.getLogger("keyboard_manager.parsers.zmk")

# Grid the frontend draws: 10 rows × 7 cols, split into left (rows 0-4) and
# right (rows 5-9). Listed here are the LIVE (physical) key positions of the
# bundled sample board, in row-major order — i.e. the order we assume the ZMK
# flat binding list follows. 60 positions. Redefine for a differently-shaped
# ZMK board (see module docstring).
GRID_ROWS = 10
GRID_COLS = 7
_LIVE_COLS_PER_ROW: list[list[int]] = [
    [0, 1, 2, 3, 4, 5],        # row 0
    [0, 1, 2, 3, 4, 5, 6],     # row 1
    [0, 1, 2, 3, 4, 5, 6],     # row 2
    [0, 1, 2, 3, 4, 5, 6],     # row 3
    [3, 4, 5],                 # row 4 (left thumbs)
    [1, 2, 3, 4, 5, 6],        # row 5
    [0, 1, 2, 3, 4, 5, 6],     # row 6
    [0, 1, 2, 3, 4, 5, 6],     # row 7
    [0, 1, 2, 3, 4, 5, 6],     # row 8
    [1, 2, 3],                 # row 9 (right thumbs)
]
DEFAULT_SLOT_MAP: list[tuple[int, int]] = [
    (r, c) for r, cols in enumerate(_LIVE_COLS_PER_ROW) for c in cols
]


class ZmkParseError(VialParseError):
    """Raised when a ZMK keymap-JSON file is malformed. Subclasses
    VialParseError so the API's existing `except VialParseError` still catches
    it."""


# ── Binding conversion ────────────────────────────────────────────────────

_MODFN_RE = re.compile(r"^([A-Z]{2})\((.*)\)$")


def _convert_keyname(token: str) -> str:
    """Convert a single ZMK key identifier (the param of `&kp`) to a QMK
    keycode string. Handles modifier functions like `LG(C)` recursively."""
    token = token.strip()
    if not token:
        return "KC_NO"
    m = _MODFN_RE.match(token)
    if m and m.group(1) in ZMK_MODFN:
        return f"{ZMK_MODFN[m.group(1)]}({_convert_keyname(m.group(2))})"
    if token in ZMK_TO_QMK:
        return ZMK_TO_QMK[token]
    if len(token) == 1 and token.isalpha():
        return f"KC_{token.upper()}"
    # Unknown — hand the raw token to the resolver, which flags it "unknown"
    # and surfaces the text so missing mappings are visible rather than hidden.
    return token


def _fallback_label(behavior: str, args: list[str]) -> str:
    """Readable text for ZMK behaviors we don't translate (bluetooth, RGB,
    bootloader, custom macros, …). Surfaced as an 'unknown' cell."""
    name = behavior.lstrip("&")
    return " ".join([name, *args]).strip() or "?"


def convert_binding(binding: str) -> str:
    """Rewrite one ZMK binding string into a QMK-style keycode the Vial
    resolver understands. Falls back to a readable label for anything exotic."""
    s = binding.strip()
    if not s:
        return "KC_NO"
    if not s.startswith("&"):
        # Some exports drop the leading `&kp` for plain keys.
        return _convert_keyname(s)

    parts = s.split()
    behavior, args = parts[0], parts[1:]

    if behavior == "&kp":
        return _convert_keyname(" ".join(args)) if args else "KC_NO"
    if behavior == "&trans":
        return "KC_TRNS"
    if behavior == "&none":
        return "KC_NO"
    if behavior == "&mo" and args:
        return f"MO({args[0]})"
    if behavior == "&to" and args:
        return f"TO({args[0]})"
    if behavior in ("&tog", "&toggle_layer") and args:
        return f"TG({args[0]})"
    if behavior == "&lt" and len(args) >= 2:
        return f"LT{args[0]}({_convert_keyname(args[1])})"
    if behavior == "&mt" and len(args) >= 2:
        mod_tap = ZMK_MOD_TO_MOD_TAP.get(args[0])
        if mod_tap:
            return f"{mod_tap}({_convert_keyname(args[1])})"
    return _fallback_label(behavior, args)


# ── Schema extraction ──────────────────────────────────────────────────────

def _binding_to_str(entry) -> str:
    """Normalize one binding entry to its ZMK string form.

    Accepts the two shapes seen in real exports:
      - a plain string:  "&kp Q"
      - keymap-editor object:  {"value": "&kp", "params": [{"value": "Q"}]}
        (params may nest for modifier functions / layer-taps)
    """
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        value = entry.get("value", "")
        params = entry.get("params", []) or []
        rendered = [value]
        for p in params:
            if isinstance(p, dict):
                pv = str(p.get("value", ""))
                pp = p.get("params", []) or []
                if pp:  # nested, e.g. LG(C)
                    inner = ",".join(str(x.get("value", "")) for x in pp if isinstance(x, dict))
                    rendered.append(f"{pv}({inner})")
                else:
                    rendered.append(pv)
            else:
                rendered.append(str(p))
        return " ".join(x for x in rendered if x).strip()
    return ""


def _extract_layers(data: dict) -> list[tuple[str, list[str]]]:
    """Return [(layer_name, [binding_str, ...]), ...] from the parsed JSON,
    tolerating the common shape variations."""
    raw_layers = data.get("layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ZmkParseError("no 'layers' array in ZMK keymap JSON")

    # `layer_names` as a sibling array is one keymap-editor variant.
    sibling_names = data.get("layer_names")

    out: list[tuple[str, list[str]]] = []
    for i, layer in enumerate(raw_layers):
        name = f"L{i}"
        bindings_src = layer
        if isinstance(layer, dict):
            name = str(layer.get("name") or layer.get("label") or name)
            bindings_src = (
                layer.get("bindings")
                if layer.get("bindings") is not None
                else layer.get("keys", [])
            )
        if isinstance(sibling_names, list) and i < len(sibling_names) and sibling_names[i]:
            name = str(sibling_names[i])
        if not isinstance(bindings_src, list):
            raise ZmkParseError(f"layer {i} ({name!r}) has no bindings list")
        out.append((name, [_binding_to_str(b) for b in bindings_src]))
    return out


def _extract_combos(data: dict, layer0_qmk: list[str]) -> list[Combo]:
    """ZMK combos reference key *positions*; map each to the converted keycode
    sitting at that position on the base layer so the frontend's combo list
    (which expects trigger keycodes) renders something meaningful."""
    raw = data.get("combos")
    if not isinstance(raw, list):
        return []
    combos: list[Combo] = []
    for ci, c in enumerate(raw):
        if not isinstance(c, dict):
            continue
        positions = c.get("keyPositions") or c.get("key_positions") or c.get("positions") or []
        triggers = [
            layer0_qmk[p]
            for p in positions
            if isinstance(p, int) and 0 <= p < len(layer0_qmk)
        ]
        binding = c.get("binding") or c.get("bindings")
        if isinstance(binding, list):
            binding = binding[0] if binding else ""
        output = convert_binding(_binding_to_str(binding)) if binding else "KC_NO"
        if triggers:
            combos.append(Combo(index=ci, triggers=triggers, output=output))
    return combos


# ── Grid mapping ─────────────────────────────────────────────────────────

def _flat_to_rows(flat_qmk: list[str], layer_index: int, layer_name: str) -> list[Row]:
    """Drop a flat binding list onto the fixed split grid using
    DEFAULT_SLOT_MAP. Positions outside the map stay None (no physical key)."""
    grid: list[list[str | None]] = [[None] * GRID_COLS for _ in range(GRID_ROWS)]
    slots = DEFAULT_SLOT_MAP
    if len(flat_qmk) != len(slots):
        logger.warning(
            "zmk layer %d (%s): %d bindings but slot map has %d — "
            "filling in order; redefine DEFAULT_SLOT_MAP for your board",
            layer_index, layer_name, len(flat_qmk), len(slots),
        )
    for i, kc in enumerate(flat_qmk):
        if i >= len(slots):
            break
        r, c = slots[i]
        grid[r][c] = kc
    return [Row(row=r, keys=grid[r]) for r in range(GRID_ROWS)]


# ── Public entry point ───────────────────────────────────────────────────

def looks_like_zmk(data: dict) -> bool:
    """Heuristic: a parsed-JSON dict is a ZMK keymap (not a Vial .vil) when it
    has no `vial_protocol` but does carry a `layers` array."""
    return (
        isinstance(data, dict)
        and "vial_protocol" not in data
        and isinstance(data.get("layers"), list)
    )


def parse(path: Path) -> Layout:
    """Load a ZMK keymap-JSON file into the shared `vial.Layout` shape.

    Raises ZmkParseError on malformed JSON or an unrecognized schema.
    """
    p = Path(path)
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ZmkParseError(f"invalid json in {p}: {e}") from e
    except FileNotFoundError as e:
        raise ZmkParseError(f"file not found: {p}") from e

    if not isinstance(data, dict):
        raise ZmkParseError("ZMK keymap JSON must be an object")

    named_layers = _extract_layers(data)

    layers: list[Layer] = []
    layer0_qmk: list[str] = []
    for li, (name, bindings) in enumerate(named_layers):
        flat_qmk = [convert_binding(b) for b in bindings]
        if li == 0:
            layer0_qmk = flat_qmk
        layers.append(Layer(index=li, rows=_flat_to_rows(flat_qmk, li, name)))

    combos = _extract_combos(data, layer0_qmk)

    logger.info(
        "parsed zmk keymap path=%s layers=%d combos=%d",
        p, len(layers), len(combos),
    )

    # ZMK has no Vial-style tap-dance / macro arrays; leave them empty. The
    # protocol field is reused as a marker (0 = not a Vial file).
    return Layout(
        vial_protocol=0,
        uid=0,
        layers=layers,
        tap_dance=[],
        combo=combos,
        macros=[],
    )
