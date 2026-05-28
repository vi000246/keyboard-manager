"""App bucket taxonomy.

Ported from ~/Projects/keyboard-map/keystat_analyze.py:20-48. Bundle IDs are
grouped into 5 buckets so the stats UI can filter by workflow context (terminal
vim/tmux vs browser BBS, etc).

Add new bundle IDs by appending them under the appropriate bucket. Unknown
bundle IDs simply get `bucket=NULL` when first seen.
"""
from __future__ import annotations

APP_BUCKETS: dict[str, list[str]] = {
    "terminal": [
        "com.googlecode.iterm2",
        "dev.warp.Warp-Stable",
        "com.apple.Terminal",
        "com.github.wez.wezterm",
    ],
    "editor": [
        "org.vim.MacVim",
        "md.obsidian",
        "notion.id",
        "com.apple.TextEdit",
    ],
    "browser": [
        "com.brave.Browser",
        "org.mozilla.firefox",
        "org.qutebrowser.qutebrowser",
        "com.google.chrome.for.testing",
    ],
    "chat": [
        "jp.naver.line.mac",
        "com.apple.MobileSMS",
        "com.apple.mail",
    ],
    "launcher": [
        "com.raycast.macos",
        "org.hammerspoon.Hammerspoon",
    ],
}

# Reverse lookup: bundle_id → bucket name. Built once on import.
_BUNDLE_TO_BUCKET: dict[str, str] = {
    bundle_id: bucket
    for bucket, bundles in APP_BUCKETS.items()
    for bundle_id in bundles
}


def bucket_for(bundle_id: str) -> str | None:
    """Return the bucket for a known bundle_id, else None."""
    return _BUNDLE_TO_BUCKET.get(bundle_id)
