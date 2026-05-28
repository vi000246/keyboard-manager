"""QMK keycode → human-readable label mapping.

Plain keycodes only. Wrapper keycodes (LT, MT, TD, LSFT, LGUI, ...) are
expanded by `backend.parsers.keycodes.resolve()`.

Keep additions alphabetical-by-category. Missing keycodes fall through to the
"unknown" branch in resolve(), which uses the raw string. The M1 coverage gate
(task 1.5) catches missing entries against the live mylayout.vil.
"""
from __future__ import annotations

KEYCODE_LABELS: dict[str, str] = {
    # ── Letters
    **{f"KC_{c}": c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    # ── Number row
    "KC_1": "1", "KC_2": "2", "KC_3": "3", "KC_4": "4", "KC_5": "5",
    "KC_6": "6", "KC_7": "7", "KC_8": "8", "KC_9": "9", "KC_0": "0",
    # ── Punctuation
    "KC_GRAVE": "`",
    "KC_MINUS": "-",
    "KC_EQUAL": "=",
    "KC_LBRC": "[",
    "KC_RBRC": "]",
    "KC_BSLS": "\\",
    "KC_SCOLON": ";",
    "KC_QUOTE": "'",
    "KC_COMMA": ",",
    "KC_DOT": ".",
    "KC_SLASH": "/",
    # ── Whitespace / editing
    "KC_SPACE": "Space",
    "KC_ENTER": "Enter",
    "KC_TAB": "Tab",
    "KC_BSPACE": "Bksp",
    "KC_DELETE": "Del",
    "KC_ESCAPE": "Esc",
    "KC_CAPS": "Caps",
    # ── Modifiers
    "KC_LSHIFT": "LShift",
    "KC_RSHIFT": "RShift",
    "KC_LCTRL": "Ctrl",
    "KC_RCTRL": "RCtrl",
    "KC_LALT": "Alt",
    "KC_RALT": "RAlt",
    "KC_LGUI": "Cmd",
    "KC_RGUI": "RCmd",
    "KC_HYPR": "Hyper",
    "KC_MEH": "Meh",
    # ── Arrows / navigation
    "KC_LEFT": "←",
    "KC_RIGHT": "→",
    "KC_UP": "↑",
    "KC_DOWN": "↓",
    "KC_PGUP": "PgUp",
    "KC_PGDOWN": "PgDn",
    "KC_HOME": "Home",
    "KC_END": "End",
    "KC_INS": "Ins",
    # ── Media
    "KC_MPLY": "Play/Pause",
    "KC_MSTP": "Stop",
    "KC_MNXT": "Next",
    "KC_MPRV": "Prev",
    "KC_MUTE": "Mute",
    "KC_VOLU": "Vol↑",
    "KC_VOLD": "Vol↓",
    "KC_BRIU": "Brt↑",
    "KC_BRID": "Brt↓",
    # ── F-keys
    **{f"KC_F{i}": f"F{i}" for i in range(1, 25)},
    # ── Audio toggle (Vial firmware feature)
    "AU_TOG": "Audio",
}
