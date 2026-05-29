"""native-helper entrypoint — pynput listener + SQLite sink + WebSocket fan-out.

Runs as a long-lived macOS host process (typically under launchd). Requires
Accessibility permission for the Python interpreter used to launch it.

Architecture:
  - pynput keyboard.Listener (background thread) fires on_press / on_release
  - We translate the key, look up the frontmost bundle id, and
      1. push the row into the EventSink buffer (batched to SQLite every 5s)
      2. schedule a dispatcher.broadcast() into the asyncio loop so all WS
         subscribers get the event in <100ms
  - The asyncio loop also hosts the websockets.serve() server on :8765
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Make the sibling `backend` package importable so we can reuse its schema bootstrap.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.db.migrations import ensure_schema  # noqa: E402

import websockets  # noqa: E402
from pynput import keyboard  # noqa: E402

from .app_tracker import current_app  # noqa: E402
from .dispatcher import EventDispatcher  # noqa: E402
from .keys import MODIFIER_NAMES, name_for  # noqa: E402
from .sink import EventSink, open_snapshot  # noqa: E402

DEFAULT_DB = Path(
    os.environ.get(
        "DB_PATH",
        str(Path.home() / "Library/Application Support/keyboard-manager/keystat.db"),
    )
)
DEFAULT_WS_HOST = os.environ.get("HELPER_WS_HOST", "0.0.0.0")
# 8765 is used by Hammerspoon's hs.httpserver on many setups; 8766 stays out
# of the way. Override with HELPER_WS_PORT if you need a different port.
DEFAULT_WS_PORT = int(os.environ.get("HELPER_WS_PORT", "8766"))

logger = logging.getLogger("native_helper")


class Helper:
    """Glues pynput → EventSink + EventDispatcher together."""

    def __init__(
        self,
        db_path: Path,
        ws_host: str = DEFAULT_WS_HOST,
        ws_port: int = DEFAULT_WS_PORT,
    ):
        self.db_path = db_path
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.sink = EventSink(db_path, source="native_helper", flush_interval=5.0)
        self.dispatcher = EventDispatcher()
        # Tracks currently-held modifier names so we can attach them to event payloads.
        self._held_mods: set[str] = set()
        # vk → name mapping for currently-pressed keys. Needed because pynput's
        # KeyCode.char shifts with the active modifier set: pressing Shift+9
        # reports char='('; if Shift releases first the same physical key's
        # release reports char='9'. Without this mapping, the WS "up" event
        # name wouldn't match the earlier "down" name and the frontend's
        # heldKeys set would leak '(' forever.
        self._pressed_names: dict[int, str] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._listener: keyboard.Listener | None = None
        self._shutdown_event: asyncio.Event | None = None

    # ── pynput callbacks (run on listener thread) ─────────────────────

    @staticmethod
    def _vk_of(key) -> int | None:
        """pynput's stable per-physical-key id. Both Key enum and KeyCode
        expose .vk on macOS; return None only for the rare case where it
        isn't present so callers can fall back to the resolved name."""
        return getattr(key, "vk", None)

    def _on_press(self, key) -> None:
        name = name_for(key)
        vk = self._vk_of(key)
        if vk is not None:
            self._pressed_names[vk] = name
        if name in MODIFIER_NAMES:
            self._held_mods.add(name)
        self._dispatch("down", name)

    def _on_release(self, key) -> None:
        vk = self._vk_of(key)
        # Prefer the name we used at press time so the release event always
        # matches its prior down (see _pressed_names docstring).
        name = self._pressed_names.pop(vk, None) if vk is not None else None
        if name is None:
            name = name_for(key)
        if name in MODIFIER_NAMES:
            self._held_mods.discard(name)
        self._dispatch("up", name)

    def _dispatch(self, event_type: str, key_name: str) -> None:
        ts = int(time.time())
        app = current_app() or "unknown"
        # Modifiers active at the moment of this event, excluding self if the
        # event itself IS a modifier.
        active = sorted(self._held_mods - ({key_name} if key_name in MODIFIER_NAMES else set()))
        mods_str = "+".join(active)

        # Persist only keydown — release events are UI-only, not part of stats.
        if event_type == "down":
            try:
                self.sink.record(
                    key=key_name, modifiers=mods_str, app_bundle=app, ts=ts
                )
            except Exception:  # noqa: BLE001
                logger.exception("sink.record failed")

        payload = {
            "type": event_type,
            "key": key_name,
            "modifiers": mods_str,
            "app": app,
            "ts": ts,
        }
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.dispatcher.broadcast(payload), self._loop
            )

    # ── WebSocket server ──────────────────────────────────────────────

    async def _ws_handler(self, websocket):
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.dispatcher.subscribe(queue)
        logger.info("ws subscriber connected; total=%d", len(self.dispatcher.subscribers))
        try:
            while True:
                msg = await queue.get()
                await websocket.send(json.dumps(msg))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.dispatcher.unsubscribe(queue)
            logger.info("ws subscriber disconnected; total=%d", len(self.dispatcher.subscribers))

    # ── lifecycle ─────────────────────────────────────────────────────

    async def run(self) -> None:
        ensure_schema(self.db_path)
        snapshot_id = open_snapshot(
            self.db_path, source="native_helper", notes="helper started"
        )
        self.sink.start(snapshot_id=snapshot_id)
        self._loop = asyncio.get_running_loop()
        self._shutdown_event = asyncio.Event()

        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()
        logger.info(
            "native-helper started: db=%s, ws=%s:%d, snapshot=%d",
            self.db_path, self.ws_host, self.ws_port, snapshot_id,
        )

        async with websockets.serve(self._ws_handler, self.ws_host, self.ws_port):
            await self._shutdown_event.wait()

        # Drain on shutdown
        if self._listener is not None:
            self._listener.stop()
        self.sink.stop()
        logger.info("native-helper stopped cleanly")

    def request_shutdown(self) -> None:
        if self._shutdown_event is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)


def _install_signal_handlers(helper: Helper) -> None:
    def _handler(signum, _frame):
        logger.info("received signal %s, shutting down", signum)
        helper.request_shutdown()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="keyboard-manager native helper")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--ws-host", default=DEFAULT_WS_HOST)
    parser.add_argument("--ws-port", type=int, default=DEFAULT_WS_PORT)
    parser.add_argument(
        "--log-level",
        default=os.environ.get("HELPER_LOG_LEVEL", "INFO"),
        help="logging level (DEBUG/INFO/WARNING/ERROR)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    helper = Helper(db_path=args.db, ws_host=args.ws_host, ws_port=args.ws_port)
    _install_signal_handlers(helper)
    try:
        asyncio.run(helper.run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
