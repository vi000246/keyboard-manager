"""Keycode resolver — expands raw Vial/QMK keycodes into human-readable labels.

Handles plain keycodes (`KC_A`), modifier wrappers (`LSFT(KC_X)`, `LGUI(KC_1)`),
mod-tap (`ALL_T(KC_SPACE)`, `LGUI_T(KC_ENTER)`), layer-tap (`LT1(KC_TAB)`), and
tap-dance (`TD(N)` with branches expanded via the supplied LayoutContext).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .keycode_labels import KEYCODE_LABELS
from .vial import TapDance


@dataclass
class LayoutContext:
    """Context required for resolving keycodes that reference other layout data.

    Currently only tap_dance lookups need this; combos are stored separately and
    rendered server-side.
    """

    tap_dance: list[TapDance | None]


@dataclass
class ResolvedKey:
    raw: str
    expanded_kind: str  # plain | layer-tap | mod-tap | tap-dance | shift-wrapped |
                        # mod-wrapped | transparent | empty | unknown
    label_top: str | None
    label_bottom: str | None = None
    tap: str | None = None
    hold: str | None = None
    double_tap: str | None = None
    tap_hold: str | None = None
    tap_term_ms: int | None = None
    branches: list[dict] = field(default_factory=list)


# Mod-tap macro → modifier label
_MOD_T_MAP: dict[str, str] = {
    "LSFT_T": "Shift",
    "RSFT_T": "RShift",
    "LCTL_T": "Ctrl",
    "RCTL_T": "RCtrl",
    "LALT_T": "Alt",
    "RALT_T": "RAlt",
    "LGUI_T": "Cmd",
    "RGUI_T": "RCmd",
    "ALL_T": "Hyper",
    "HYPR_T": "Hyper",
    "MEH_T": "Meh",
}

# Modifier wrapper macros → label prefix
_MOD_WRAP_MAP: dict[str, str] = {
    "LCTL": "Ctrl",
    "RCTL": "RCtrl",
    "LALT": "Alt",
    "RALT": "RAlt",
    "LGUI": "Cmd",
    "RGUI": "RCmd",
    # LSFT handled separately because of shift-pair labels (KC_1 → "!" etc.)
}

# Shifted variants of common keys — produced when wrapped in LSFT(...)
_SHIFT_PAIRS: dict[str, str] = {
    "KC_1": "!", "KC_2": "@", "KC_3": "#", "KC_4": "$", "KC_5": "%",
    "KC_6": "^", "KC_7": "&", "KC_8": "*", "KC_9": "(", "KC_0": ")",
    "KC_SCOLON": ":", "KC_QUOTE": '"',
    "KC_COMMA": "<", "KC_DOT": ">", "KC_SLASH": "?",
    "KC_MINUS": "_", "KC_EQUAL": "+",
    "KC_LBRC": "{", "KC_RBRC": "}", "KC_BSLS": "|", "KC_GRAVE": "~",
}


def _strip_wrapper(raw: str, prefix: str) -> str | None:
    """If raw is `{prefix}(...)`, return the inner string. Else None."""
    open_ = f"{prefix}("
    if raw.startswith(open_) and raw.endswith(")"):
        return raw[len(open_):-1]
    return None


def resolve(raw: str, ctx: LayoutContext) -> ResolvedKey:
    """Expand a single Vial keycode to a ResolvedKey for frontend rendering."""
    # ── Sentinel / no-key
    if raw == "KC_NO":
        return ResolvedKey(raw=raw, expanded_kind="empty", label_top=None)
    if raw == "KC_TRNS":
        return ResolvedKey(raw=raw, expanded_kind="transparent", label_top=None)

    # ── Plain keycode lookup
    if raw in KEYCODE_LABELS:
        return ResolvedKey(raw=raw, expanded_kind="plain", label_top=KEYCODE_LABELS[raw])

    # ── LSFT(...) shift wrapper — produces a shifted-glyph label
    inner = _strip_wrapper(raw, "LSFT")
    if inner is not None:
        if inner in _SHIFT_PAIRS:
            return ResolvedKey(
                raw=raw, expanded_kind="shift-wrapped",
                label_top=_SHIFT_PAIRS[inner],
            )
        inner_lbl = resolve(inner, ctx).label_top or inner
        return ResolvedKey(
            raw=raw, expanded_kind="shift-wrapped",
            label_top=f"⇧{inner_lbl}",
        )

    # ── Other mod wrappers: LCTL(...), LALT(...), LGUI(...), RCTL(...), RALT(...), RGUI(...)
    for prefix, mod_label in _MOD_WRAP_MAP.items():
        inner = _strip_wrapper(raw, prefix)
        if inner is not None:
            inner_lbl = resolve(inner, ctx).label_top or inner
            return ResolvedKey(
                raw=raw, expanded_kind="mod-wrapped",
                label_top=f"{mod_label}+{inner_lbl}",
            )

    # ── LT{N}(KC_X) layer-tap
    if raw.startswith("LT") and "(" in raw and raw.endswith(")"):
        layer_str = raw[2:raw.index("(")]
        if layer_str.isdigit():
            layer = int(layer_str)
            inner = raw[raw.index("(") + 1 : -1]
            inner_lbl = resolve(inner, ctx).label_top
            return ResolvedKey(
                raw=raw, expanded_kind="layer-tap",
                label_top=inner_lbl, label_bottom=f"→L{layer}",
                tap=inner_lbl, hold=f"→L{layer}",
            )

    # ── Mod-tap macros (ALL_T, LGUI_T, LCTL_T, …)
    for mod_t, mod_label in _MOD_T_MAP.items():
        inner = _strip_wrapper(raw, mod_t)
        if inner is not None:
            inner_lbl = resolve(inner, ctx).label_top
            return ResolvedKey(
                raw=raw, expanded_kind="mod-tap",
                label_top=inner_lbl, label_bottom=mod_label,
                tap=inner_lbl, hold=mod_label,
            )

    # ── TD(N) tap-dance — pull branches from context
    if raw.startswith("TD(") and raw.endswith(")"):
        idx_str = raw[3:-1]
        if idx_str.isdigit():
            idx = int(idx_str)
            td = ctx.tap_dance[idx] if 0 <= idx < len(ctx.tap_dance) else None
            if td is None:
                return ResolvedKey(
                    raw=raw, expanded_kind="tap-dance",
                    label_top=f"TD{idx}", label_bottom=None,
                )
            tap_r = resolve(td.tap, ctx)
            hold_r = resolve(td.hold, ctx)
            dt_r = resolve(td.double_tap, ctx)
            th_r = resolve(td.tap_hold, ctx)
            return ResolvedKey(
                raw=raw, expanded_kind="tap-dance",
                label_top=tap_r.label_top, label_bottom=f"TD{idx}",
                tap=tap_r.label_top,
                hold=hold_r.label_top,
                double_tap=dt_r.label_top,
                tap_hold=th_r.label_top,
                tap_term_ms=td.tap_term_ms,
                branches=[
                    {"action": "tap", "label": tap_r.label_top},
                    {"action": "hold", "label": hold_r.label_top},
                    {"action": "double_tap", "label": dt_r.label_top},
                    {"action": "tap_hold", "label": th_r.label_top},
                ],
            )

    # ── Fallback: surface raw so the M1 coverage gate flags missing labels
    return ResolvedKey(raw=raw, expanded_kind="unknown", label_top=raw)
