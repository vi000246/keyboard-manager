import pytest


def test_current_app_returns_string_or_none():
    """On macOS with NSWorkspace, returns the frontmost bundle id; on Linux, None."""
    pytest.importorskip("AppKit")
    from native_helper.app_tracker import _reset_cache_for_test, current_app

    _reset_cache_for_test()
    r = current_app()
    assert r is None or isinstance(r, str)
    if isinstance(r, str):
        # Bundle IDs are reverse-DNS strings
        assert "." in r


def test_caches_within_ttl(monkeypatch):
    """Second call within 100ms must not re-invoke NSWorkspace."""
    pytest.importorskip("AppKit")
    from native_helper import app_tracker

    app_tracker._reset_cache_for_test()
    call_count = {"n": 0}
    real_ws = app_tracker.NSWorkspace
    if real_ws is None:
        pytest.skip("NSWorkspace not available on this platform")

    class _SpyWorkspace:
        @staticmethod
        def sharedWorkspace():
            call_count["n"] += 1
            return real_ws.sharedWorkspace()

    monkeypatch.setattr(app_tracker, "NSWorkspace", _SpyWorkspace)

    app_tracker.current_app()
    app_tracker.current_app()
    app_tracker.current_app()
    assert call_count["n"] == 1, "second/third calls within TTL must hit cache"
