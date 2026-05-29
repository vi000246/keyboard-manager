"""Keystat event-key helpers.

Ported from docs/keyboard-map/keystat_analyze.py (lines 60-68). The
sibling project's logic has been validated against 8 days / 137k keystrokes;
this is a verbatim port plus `serialize_mods` for consistent SQLite storage.
"""
from __future__ import annotations


def is_modifier_combo(key: str) -> bool:
    """True if the key string includes one or more modifier prefixes."""
    return "+" in key


def split_mods(key: str) -> tuple[frozenset[str], str]:
    """Split a `mod1+mod2+base` string into (frozenset of mods, base key)."""
    parts = key.split("+")
    return frozenset(parts[:-1]), parts[-1]


def serialize_mods(mods: frozenset[str]) -> str:
    """Stable string form of a modifier set — alphabetical, '+'-joined.

    Empty set → empty string. Used as the canonical SQLite `modifiers` value.
    """
    return "+".join(sorted(mods))
