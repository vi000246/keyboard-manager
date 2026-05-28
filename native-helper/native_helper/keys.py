"""Translate pynput Key / KeyCode events into stable string names.

pynput's `key` argument is either:
  - `pynput.keyboard.KeyCode` with a `.char` attribute (single character keys), or
  - `pynput.keyboard.Key` enum member (Key.space, Key.shift_l, ...).

We map both into the same lowercase string vocabulary that
`backend/db/heatmap_mapper.py:_EVENT_KEY_ALIASES` already knows about
("space", "return", "left", "shift", ...), so the heatmap lookup stays
consistent between the JSON baseline and the native-helper stream.
"""
from __future__ import annotations

# Pynput Key enum names that map to our canonical lowercase strings.
# Anything not in this map falls through to repr() with the "Key." prefix stripped.
_KEY_NAME_MAP: dict[str, str] = {
    # Whitespace / editing
    "space": "space",
    "enter": "return",
    "tab": "tab",
    "backspace": "delete",     # pynput "backspace" → macOS event name "delete"
    "delete": "forwarddelete", # pynput "delete" key (fn+backspace) → forward delete
    "esc": "escape",
    # Navigation
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
    "home": "home",
    "end": "end",
    "page_up": "pageup",
    "page_down": "pagedown",
    # Modifiers — both sides report individually
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "ctrl":  "ctrl",  "ctrl_l":  "ctrl",  "ctrl_r":  "ctrl",
    "alt":   "alt",   "alt_l":   "alt",   "alt_r":   "alt",
    "cmd":   "cmd",   "cmd_l":   "cmd",   "cmd_r":   "cmd",
    "caps_lock": "capslock",
}

# Which canonical names are modifiers (used for chord detection later)
MODIFIER_NAMES: frozenset[str] = frozenset({"shift", "ctrl", "alt", "cmd"})


def name_for(key) -> str:
    """Return a stable lowercase string for a pynput Key or KeyCode."""
    # KeyCode case — `.char` is a printable string (or None for unmapped scancodes)
    char = getattr(key, "char", None)
    if char is not None:
        return char.lower()

    # Key enum case — `str(Key.space)` == "Key.space"
    raw = str(key)
    if raw.startswith("Key."):
        raw = raw[4:]
    return _KEY_NAME_MAP.get(raw, raw)
