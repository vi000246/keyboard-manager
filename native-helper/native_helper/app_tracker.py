"""Frontmost-app tracker via NSWorkspace.

Caches the result for 100ms to avoid hammering the AppKit bridge when the user
is typing fast (the bundle ID rarely changes within that window).
"""
from __future__ import annotations

import time

try:
    from AppKit import NSWorkspace
except ImportError:  # pragma: no cover — Linux/CI without pyobjc
    NSWorkspace = None  # type: ignore[assignment]

_CACHE: dict[str, object] = {"ts": 0.0, "value": None}
_CACHE_TTL_SEC = 0.1


def current_app() -> str | None:
    """Return the frontmost app's bundle identifier, or None if unavailable."""
    now = time.monotonic()
    if now - _CACHE["ts"] < _CACHE_TTL_SEC:  # type: ignore[operator]
        return _CACHE["value"]  # type: ignore[return-value]
    if NSWorkspace is None:
        return None
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    bundle_id = app.bundleIdentifier() if app else None
    _CACHE["ts"] = now
    _CACHE["value"] = bundle_id
    return bundle_id


def _reset_cache_for_test() -> None:
    """Test helper — drop the cached value so the next call hits NSWorkspace."""
    _CACHE["ts"] = 0.0
    _CACHE["value"] = None
