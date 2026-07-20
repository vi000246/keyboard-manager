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
    # Older QMK aliases — same physical key, different name. Vial sometimes
    # serializes the long form (KC_LBRACKET) instead of the short (KC_LBRC),
    # so we accept both rather than asking the user to re-save their layout.
    "KC_LBRACKET": "[",
    "KC_RBRACKET": "]",
    "KC_BSLASH": "\\",
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
    # ── HID Application Control — system-wide edit actions. macOS routes
    # these to the focused app's standard Edit menu.
    "KC_COPY":  "Copy",
    "KC_CUT":   "Cut",
    "KC_PSTE":  "Paste",  # short form; some firmwares serialize KC_PASTE too
    "KC_PASTE": "Paste",
    "KC_UNDO":  "Undo",
    "KC_AGAIN": "Redo",   # HID "Again" — Linux Redo; on macOS often unbound
    "KC_FIND":  "Find",
    # ── HID Browser Control
    "KC_WBAK":  "Browser ←",
    "KC_WFWD":  "Browser →",
    "KC_WHOM":  "Browser Home",
    "KC_WSCH":  "Browser Search",
    "KC_WSTP":  "Browser Stop",
    "KC_WREF":  "Browser Reload",
    "KC_WFAV":  "Browser Favs",
    # ── Vial layer-lock — toggles a "stick the active layer until tapped
    # again" state. Useful for hold-free NAV / SYM usage.
    "QK_LAYER_LOCK": "Lock layer",
    # ── Keypad. Distinct HID usages from the number row, so a NUM layer built
    # on KC_KP_* needs its own entries. Labelled "Num N" rather than bare "N"
    # so the tooltip disambiguates them from KC_1..KC_0; a user-defined name
    # still overrides what the cell displays.
    **{f"KC_KP_{i}": f"Num {i}" for i in range(10)},
    "KC_KP_DOT": "Num .",
    "KC_KP_COMMA": "Num ,",
    "KC_KP_PLUS": "Num +",
    "KC_KP_MINUS": "Num -",
    "KC_KP_ASTERISK": "Num *",
    "KC_KP_SLASH": "Num /",
    "KC_KP_EQUAL": "Num =",
    "KC_KP_ENTER": "Num Enter",
    # ── Mouse keys. KC_BTN* are clicks; KC_MS_* move the pointer and
    # KC_WH_* scroll — three different things that are easy to conflate.
    "KC_BTN1": "Click L",
    "KC_BTN2": "Click R",
    "KC_BTN3": "Click M",
    "KC_BTN4": "Click 4",
    "KC_BTN5": "Click 5",
    "KC_MS_U": "Mouse ↑",
    "KC_MS_D": "Mouse ↓",
    "KC_MS_L": "Mouse ←",
    "KC_MS_R": "Mouse →",
    "KC_WH_U": "Wheel ↑",
    "KC_WH_D": "Wheel ↓",
    "KC_WH_L": "Wheel ←",
    "KC_WH_R": "Wheel →",
    # ── System / lock keys. Vial serializes the long forms.
    "KC_PSCREEN": "PrtSc",
    "KC_PSCR": "PrtSc",
    "KC_SCROLLLOCK": "ScrLk",
    "KC_PAUSE": "Pause",
    "KC_NUMLOCK": "NumLk",
}
