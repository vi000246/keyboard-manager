"""Helper press/release name pairing.

Regression: pynput KeyCode.char shifts with the active modifier state, so
the release event for a physical key may not carry the same name as its
earlier press (e.g. press '(' while Shift held → release '9' after Shift
went up first). The Helper compensates by remembering the press-time name
keyed by .vk and reusing it on release.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from native_helper.main import Helper


class _KeyCodeStub:
    """Stand-in for pynput.keyboard.KeyCode with `.char` AND `.vk`."""

    def __init__(self, char: str, vk: int):
        self.char = char
        self.vk = vk


class _KeyEnumStub:
    """Stand-in for pynput.keyboard.Key — has `.vk`, no `.char`."""

    def __init__(self, name: str, vk: int):
        self.name = name
        self.vk = vk
        self.char = None

    def __str__(self) -> str:
        return f"Key.{self.name}"


@pytest.fixture
def helper(tmp_path: Path) -> Helper:
    # Bypass sink/dispatcher I/O — we only care about _dispatch's name argument.
    h = Helper(db_path=tmp_path / "t.db")
    h._dispatch = MagicMock()  # type: ignore[method-assign]
    return h


def test_release_uses_press_time_name_when_char_shifts(helper: Helper) -> None:
    """Press '(' (Shift held), release '9' (Shift gone) — release event must
    still dispatch 'up' for '(', not '9'."""
    press_key = _KeyCodeStub(char="(", vk=25)
    release_key = _KeyCodeStub(char="9", vk=25)

    helper._on_press(press_key)
    helper._on_release(release_key)

    calls = helper._dispatch.call_args_list
    assert calls[0].args == ("down", "(")
    assert calls[1].args == ("up", "(")


def test_release_falls_back_to_name_for_when_vk_missing(helper: Helper) -> None:
    """If a key arrives without .vk (defensive), we still produce a sane name."""
    class _NoVk:
        char = "x"
        vk = None

    helper._on_release(_NoVk())
    helper._dispatch.assert_called_once_with("up", "x")


def test_modifier_held_set_tracks_press_and_release(helper: Helper) -> None:
    shift = _KeyEnumStub("shift_l", vk=56)
    helper._on_press(shift)
    assert "shift" in helper._held_mods
    helper._on_release(shift)
    assert "shift" not in helper._held_mods


def test_pressed_names_cleared_after_release(helper: Helper) -> None:
    k = _KeyCodeStub(char="j", vk=38)
    helper._on_press(k)
    assert helper._pressed_names == {38: "j"}
    helper._on_release(k)
    assert helper._pressed_names == {}
