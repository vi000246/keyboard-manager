from backend.parsers.keystat_keys import (
    is_modifier_combo,
    serialize_mods,
    split_mods,
)


def test_plain_key_not_combo():
    assert is_modifier_combo("j") is False


def test_combo_with_mod():
    assert is_modifier_combo("cmd+v") is True


def test_split_plain():
    mods, base = split_mods("j")
    assert mods == frozenset()
    assert base == "j"


def test_split_single_mod():
    mods, base = split_mods("cmd+v")
    assert mods == frozenset({"cmd"})
    assert base == "v"


def test_split_multi_mod():
    mods, base = split_mods("cmd+ctrl+alt+1")
    assert mods == frozenset({"cmd", "ctrl", "alt"})
    assert base == "1"


def test_serialize_mods_is_alphabetical():
    s = serialize_mods(frozenset({"cmd", "ctrl", "alt"}))
    assert s == "alt+cmd+ctrl"


def test_serialize_empty_is_empty_string():
    assert serialize_mods(frozenset()) == ""


def test_roundtrip_preserves_set():
    raw = "cmd+ctrl+alt+space"
    mods, base = split_mods(raw)
    rebuilt = serialize_mods(mods) + "+" + base
    # Order differs from raw but set membership is preserved
    rebuilt_mods, rebuilt_base = split_mods(rebuilt)
    assert rebuilt_mods == mods
    assert rebuilt_base == base
