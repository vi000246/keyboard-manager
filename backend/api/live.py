"""WebSocket reverse proxy /api/live → native-helper :8765.

Browsers connect to nginx :8081 → backend :8000 /api/live. We dial the
host-side helper at HELPER_WS_URL and forward messages transparently. If
the helper is unreachable, we emit a single helper_disconnected frame and
close so the frontend can show a clear status.
"""
from __future__ import annotations

import asyncio
import logging
import os

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger("keyboard_manager.api.live")

HELPER_URL = os.environ.get("HELPER_WS_URL", "ws://host.docker.internal:8765")


@router.websocket("/api/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()

    try:
        upstream = await asyncio.wait_for(
            websockets.connect(HELPER_URL, open_timeout=2), timeout=3
        )
    except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as e:
        logger.warning("helper unreachable at %s: %s", HELPER_URL, e)
        try:
            await ws.send_json({"type": "helper_disconnected", "ts": 0, "reason": str(e)})
        finally:
            await ws.close()
        return

    try:
        async for msg in upstream:
            # Helper sends strings (JSON); forward verbatim.
            await ws.send_text(msg)
    except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed):
        pass
    finally:
        await upstream.close()
