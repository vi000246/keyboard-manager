"""Helper status endpoint.

Reports two independent signals so the UI can distinguish "helper is running
but you've been idle" from "helper crashed":

  process_running   — TCP connect + WebSocket upgrade to HELPER_WS_URL works
  last_event_ts     — epoch second of the latest `native_helper` event in DB
  recently_captured — last event within RECENT_WINDOW_SEC seconds
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time

import websockets
from fastapi import APIRouter

logger = logging.getLogger("keyboard_manager.api.helper")
router = APIRouter()

HELPER_URL = os.environ.get("HELPER_WS_URL", "ws://host.docker.internal:8766")
PROBE_TIMEOUT_SEC = float(os.environ.get("HELPER_PROBE_TIMEOUT_SEC", "1.5"))
RECENT_WINDOW_SEC = int(os.environ.get("HELPER_RECENT_WINDOW_SEC", "300"))  # 5 min


@router.get("/api/helper/status")
async def get_status() -> dict:
    from ..main import DB_PATH

    process_running = await _probe_helper()
    last_event_ts = _last_event_ts(DB_PATH)
    now = int(time.time())
    seconds_since = (now - last_event_ts) if last_event_ts else None
    recently_captured = bool(seconds_since is not None and seconds_since <= RECENT_WINDOW_SEC)

    return {
        "process_running": process_running,
        "last_event_ts": last_event_ts,
        "seconds_since_last_event": seconds_since,
        "recently_captured": recently_captured,
        "recent_window_sec": RECENT_WINDOW_SEC,
        "helper_url": HELPER_URL,
    }


async def _probe_helper() -> bool:
    """Try a quick WS connect + close. True if the helper accepted us."""
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SEC):
            async with websockets.connect(HELPER_URL, open_timeout=PROBE_TIMEOUT_SEC):
                return True
    except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as e:
        logger.debug("helper probe failed: %s", e)
        return False


def _last_event_ts(db_path) -> int | None:
    """Highest ts on a native_helper event, or None if there are none yet."""
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            "SELECT MAX(ts) FROM events WHERE source = 'native_helper'"
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()
