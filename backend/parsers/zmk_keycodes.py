"""ZMK key-name → QMK keycode lookup tables.

The ZMK parser (`zmk.py`) converts ZMK keymap bindings into the *same*
QMK-style keycode strings the Vial pipeline already understands (`KC_Q`,
`LT1(KC_TAB)`, `LSFT(KC_1)`, …). That lets the existing `keycodes.resolve()`
expander, the layout serializer, and the whole frontend work on ZMK layouts
with zero changes — only this name mapping is ZMK-specific.

ZMK key identifiers come from `dt-bindings/zmk/keys.h`. We cover the common
ones; anything unmapped falls through to a best-effort label in `zmk.py`.
"""
from __future__ import annotations

# ── Modifier *functions* used inside `&kp` params: ZMK `LG(C)` == left-GUI + C.
# Maps the ZMK 2-letter function to the QMK wrapper macro `keycodes.resolve()`
# already expands.
ZMK_MODFN: dict[str, str] = {
    "LS": "LSFT", "RS": "RSFT",
    "LC": "LCTL", "RC": "RCTL",
    "LA": "LALT", "RA": "RALT",
    "LG": "LGUI", "RG": "RGUI",
}

# ── `&mt <MOD> <KEY>` hold-modifier → QMK mod-tap macro.
ZMK_MOD_TO_MOD_TAP: dict[str, str] = {
    "LSHFT": "LSFT_T", "LSHIFT": "LSFT_T", "LEFT_SHIFT": "LSFT_T",
    "RSHFT": "RSFT_T", "RSHIFT": "RSFT_T", "RIGHT_SHIFT": "RSFT_T",
    "LCTRL": "LCTL_T", "LCTL": "LCTL_T", "LEFT_CONTROL": "LCTL_T",
    "RCTRL": "RCTL_T", "RCTL": "RCTL_T", "RIGHT_CONTROL": "RCTL_T",
    "LALT": "LALT_T", "LEFT_ALT": "LALT_T",
    "RALT": "RALT_T", "RIGHT_ALT": "RALT_T",
    "LGUI": "LGUI_T", "LCMD": "LGUI_T", "LWIN": "LGUI_T", "LEFT_GUI": "LGUI_T",
    "RGUI": "RGUI_T", "RCMD": "RGUI_T", "RWIN": "RGUI_T", "RIGHT_GUI": "RGUI_T",
}


def _build_map() -> dict[str, str]:
    m: dict[str, str] = {}

    # Letters A-Z and digits.
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        m[c] = f"KC_{c}"
    for d in range(1, 10):
        m[f"N{d}"] = f"KC_{d}"
        m[f"NUMBER_{d}"] = f"KC_{d}"
    m["N0"] = "KC_0"
    m["NUMBER_0"] = "KC_0"

    # Function row.
    for n in range(1, 25):
        m[f"F{n}"] = f"KC_F{n}"

    named = {
        # whitespace / control
        "SPACE": "KC_SPACE",
        "TAB": "KC_TAB",
        "RET": "KC_ENTER", "RETURN": "KC_ENTER", "ENTER": "KC_ENTER",
        "ESC": "KC_ESCAPE", "ESCAPE": "KC_ESCAPE",
        "BSPC": "KC_BSPACE", "BACKSPACE": "KC_BSPACE",
        "DEL": "KC_DELETE", "DELETE": "KC_DELETE",
        "INS": "KC_INS", "INSERT": "KC_INS",
        "CAPS": "KC_CAPS", "CAPSLOCK": "KC_CAPS", "CLCK": "KC_CAPS",
        # navigation
        "HOME": "KC_HOME", "END": "KC_END",
        "PG_UP": "KC_PGUP", "PAGE_UP": "KC_PGUP", "PGUP": "KC_PGUP",
        "PG_DN": "KC_PGDOWN", "PAGE_DOWN": "KC_PGDOWN", "PGDN": "KC_PGDOWN",
        "LEFT": "KC_LEFT", "LEFT_ARROW": "KC_LEFT",
        "RIGHT": "KC_RIGHT", "RIGHT_ARROW": "KC_RIGHT",
        "UP": "KC_UP", "UP_ARROW": "KC_UP",
        "DOWN": "KC_DOWN", "DOWN_ARROW": "KC_DOWN",
        # modifiers as plain keys
        "LSHFT": "KC_LSHIFT", "LSHIFT": "KC_LSHIFT", "LEFT_SHIFT": "KC_LSHIFT",
        "RSHFT": "KC_RSHIFT", "RSHIFT": "KC_RSHIFT", "RIGHT_SHIFT": "KC_RSHIFT",
        "LCTRL": "KC_LCTRL", "LCTL": "KC_LCTRL", "LEFT_CONTROL": "KC_LCTRL",
        "RCTRL": "KC_RCTRL", "RCTL": "KC_RCTRL", "RIGHT_CONTROL": "KC_RCTRL",
        "LALT": "KC_LALT", "LEFT_ALT": "KC_LALT",
        "RALT": "KC_RALT", "RIGHT_ALT": "KC_RALT",
        "LGUI": "KC_LGUI", "LCMD": "KC_LGUI", "LWIN": "KC_LGUI", "LEFT_GUI": "KC_LGUI",
        "RGUI": "KC_RGUI", "RCMD": "KC_RGUI", "RWIN": "KC_RGUI", "RIGHT_GUI": "KC_RGUI",
        # base punctuation
        "MINUS": "KC_MINUS",
        "EQUAL": "KC_EQUAL",
        "LBKT": "KC_LBRC", "LEFT_BRACKET": "KC_LBRC",
        "RBKT": "KC_RBRC", "RIGHT_BRACKET": "KC_RBRC",
        "BSLH": "KC_BSLS", "BACKSLASH": "KC_BSLS",
        "SEMI": "KC_SCOLON", "SEMICOLON": "KC_SCOLON",
        "SQT": "KC_QUOTE", "APOS": "KC_QUOTE", "APOSTROPHE": "KC_QUOTE",
        "SINGLE_QUOTE": "KC_QUOTE",
        "GRAVE": "KC_GRAVE",
        "COMMA": "KC_COMMA",
        "DOT": "KC_DOT", "PERIOD": "KC_DOT",
        "FSLH": "KC_SLASH", "SLASH": "KC_SLASH",
        "NON_US_BSLH": "KC_BSLS",
        # shifted symbols — ZMK exposes pre-shifted names; map to LSFT(base) so
        # the resolver renders the glyph (e.g. "!" instead of "Shift+1").
        "EXCL": "LSFT(KC_1)", "EXCLAMATION": "LSFT(KC_1)",
        "AT": "LSFT(KC_2)", "AT_SIGN": "LSFT(KC_2)",
        "HASH": "LSFT(KC_3)", "POUND": "LSFT(KC_3)",
        "DLLR": "LSFT(KC_4)", "DOLLAR": "LSFT(KC_4)",
        "PRCNT": "LSFT(KC_5)", "PERCENT": "LSFT(KC_5)",
        "CARET": "LSFT(KC_6)",
        "AMPS": "LSFT(KC_7)", "AMPERSAND": "LSFT(KC_7)",
        "STAR": "LSFT(KC_8)", "ASTERISK": "LSFT(KC_8)", "ASTRK": "LSFT(KC_8)",
        "LPAR": "LSFT(KC_9)", "LEFT_PARENTHESIS": "LSFT(KC_9)",
        "RPAR": "LSFT(KC_0)", "RIGHT_PARENTHESIS": "LSFT(KC_0)",
        "UNDER": "LSFT(KC_MINUS)", "UNDERSCORE": "LSFT(KC_MINUS)",
        "PLUS": "LSFT(KC_EQUAL)",
        "LBRC": "LSFT(KC_LBRC)", "LEFT_BRACE": "LSFT(KC_LBRC)",
        "RBRC": "LSFT(KC_RBRC)", "RIGHT_BRACE": "LSFT(KC_RBRC)",
        "PIPE": "LSFT(KC_BSLS)",
        "COLON": "LSFT(KC_SCOLON)",
        "DQT": "LSFT(KC_QUOTE)", "DOUBLE_QUOTES": "LSFT(KC_QUOTE)",
        "LT": "LSFT(KC_COMMA)", "LESS_THAN": "LSFT(KC_COMMA)",
        "GT": "LSFT(KC_DOT)", "GREATER_THAN": "LSFT(KC_DOT)",
        "QMARK": "LSFT(KC_SLASH)", "QUESTION": "LSFT(KC_SLASH)",
        "TILDE": "LSFT(KC_GRAVE)", "TILDE2": "LSFT(KC_GRAVE)",
        # media / consumer
        "C_PP": "KC_MPLY", "C_PLAY_PAUSE": "KC_MPLY",
        "C_NEXT": "KC_MNXT", "C_PREV": "KC_MPRV", "C_STOP": "KC_MSTP",
        "C_VOL_UP": "KC_VOLU", "C_VOLUME_UP": "KC_VOLU",
        "C_VOL_DN": "KC_VOLD", "C_VOLUME_DOWN": "KC_VOLD",
        "C_MUTE": "KC_MUTE",
    }
    m.update(named)
    return m


# ZMK key identifier → QMK keycode (or a QMK wrapper string for shifted glyphs).
ZMK_TO_QMK: dict[str, str] = _build_map()
