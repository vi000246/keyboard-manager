"""Tests for the key-name normalizer.

Uses lightweight stub objects instead of importing pynput so the test suite
runs in any environment (CI, Linux dev machine without macOS accessibility).
"""
from native_helper.keys import MODIFIER_NAMES, name_for


class _KeyCodeStub:
    """Stand-in for pynput.keyboard.KeyCode — has a `.char` attribute."""

    def __init__(self, char):
        self.char = char

    def __repr__(self) -> str:
        return f"<KeyCode char={self.char!r}>"


class _KeyEnumStub:
    """Stand-in for pynput.keyboard.Key members — str() returns 'Key.name'."""

    def __init__(self, name):
        self.name = name
        self.char = None  # KeyEnum has no char attribute in pynput; we mirror that

    def __str__(self) -> str:
        return f"Key.{self.name}"


def test_keycode_letter():
    assert name_for(_KeyCodeStub("J")) == "j"
    assert name_for(_KeyCodeStub("k")) == "k"


def test_keycode_punctuation():
    assert name_for(_KeyCodeStub(";")) == ";"


def test_key_enum_space_maps_to_space():
    assert name_for(_KeyEnumStub("space")) == "space"


def test_key_enum_enter_maps_to_return():
    """pynput uses 'enter'; our event vocabulary uses 'return' (macOS)."""
    assert name_for(_KeyEnumStub("enter")) == "return"


def test_key_enum_backspace_maps_to_delete():
    assert name_for(_KeyEnumStub("backspace")) == "delete"


def test_key_enum_arrows():
    assert name_for(_KeyEnumStub("left")) == "left"
    assert name_for(_KeyEnumStub("right")) == "right"


def test_key_enum_modifier_aliases():
    """shift_l / shift_r both collapse to 'shift'."""
    assert name_for(_KeyEnumStub("shift_l")) == "shift"
    assert name_for(_KeyEnumStub("shift_r")) == "shift"
    assert name_for(_KeyEnumStub("cmd_r")) == "cmd"


def test_key_enum_unknown_falls_through():
    """Unknown Key.* values are returned with the prefix stripped, lowercased."""
    assert name_for(_KeyEnumStub("media_play_pause")) == "media_play_pause"


def test_modifier_names_set():
    assert MODIFIER_NAMES == frozenset({"shift", "ctrl", "alt", "cmd"})
