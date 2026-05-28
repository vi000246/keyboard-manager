"""Friendly display names for macOS bundle IDs.

The bundle id (e.g. `com.googlecode.iterm2`) is what NSWorkspace reports, but
it's not what the user sees in Dock / Cmd-Tab. This module maps known bundles
to their human display name, with a heuristic fallback for unknown bundles.

Add new entries as you encounter them — the heuristic is just a safety net.
"""
from __future__ import annotations

# Known bundle id → display name. Keep alphabetical by display name for easy
# scanning when adding entries.
KNOWN_DISPLAY_NAMES: dict[str, str] = {
    # Terminals
    "com.googlecode.iterm2":          "iTerm",
    "com.apple.Terminal":             "Terminal",
    "com.github.wez.wezterm":         "WezTerm",
    "dev.warp.Warp-Stable":           "Warp",
    # Editors / notes
    "org.vim.MacVim":                 "MacVim",
    "md.obsidian":                    "Obsidian",
    "notion.id":                      "Notion",
    "com.apple.TextEdit":             "TextEdit",
    # Browsers
    "com.brave.Browser":              "Brave",
    "org.mozilla.firefox":            "Firefox",
    "com.google.chrome.for.testing":  "Chrome (Testing)",
    "org.qutebrowser.qutebrowser":    "qutebrowser",
    "com.apple.Safari":               "Safari",
    # Chat / mail
    "jp.naver.line.mac":              "LINE",
    "com.apple.MobileSMS":            "Messages",
    "com.apple.mail":                 "Mail",
    "com.tdesktop.Telegram":          "Telegram",
    "com.tinyspeck.slackmacgap":      "Slack",
    # Launchers / automation
    "com.raycast.macos":              "Raycast",
    "org.hammerspoon.Hammerspoon":    "Hammerspoon",
    "com.apple.spotlight":            "Spotlight",
    # System
    "com.apple.systempreferences":    "System Settings",
    "com.apple.finder":               "Finder",
    "com.apple.dock":                 "Dock",
    "com.apple.AppStore":             "App Store",
    "com.apple.KeyboardSetupAssistant": "Keyboard Setup Assistant",
    # Common dev tools
    "com.docker.docker":              "Docker Desktop",
    "com.todesktop.230313mzl4w4u92":  "Cursor",
    "com.microsoft.VSCode":           "VS Code",
}


def friendly_name(bundle_id: str | None) -> str:
    """Return a human-readable name for ``bundle_id``.

    1. Exact match in KNOWN_DISPLAY_NAMES wins.
    2. Otherwise, take the last reverse-DNS segment and title-case it. This
       keeps strange bundle IDs at least readable
       (``foo.bar.MyCoolApp`` → ``MyCoolApp``).
    3. If ``bundle_id`` is empty / None, return "(unknown)".
    """
    if not bundle_id:
        return "(unknown)"
    if bundle_id in KNOWN_DISPLAY_NAMES:
        return KNOWN_DISPLAY_NAMES[bundle_id]
    tail = bundle_id.rsplit(".", 1)[-1] if "." in bundle_id else bundle_id
    return tail or bundle_id
