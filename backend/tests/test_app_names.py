from backend.db.app_names import KNOWN_DISPLAY_NAMES, friendly_name


def test_known_bundle():
    assert friendly_name("md.obsidian") == "Obsidian"
    assert friendly_name("com.brave.Browser") == "Brave"
    assert friendly_name("org.hammerspoon.Hammerspoon") == "Hammerspoon"


def test_unknown_falls_back_to_tail():
    assert friendly_name("io.example.MyCoolApp") == "MyCoolApp"


def test_no_dot_returns_as_is():
    assert friendly_name("standalone") == "standalone"


def test_empty_or_none_returns_unknown_placeholder():
    assert friendly_name("") == "(unknown)"
    assert friendly_name(None) == "(unknown)"


def test_known_map_has_no_duplicate_display_names_for_same_bundle():
    """Spot-check the table: each bundle id maps to exactly one name."""
    assert len(KNOWN_DISPLAY_NAMES) == len(set(KNOWN_DISPLAY_NAMES))
