"""Fan-out event dispatcher for WebSocket subscribers.

Each connected browser tab gets its own asyncio.Queue. The pynput listener
thread calls ``broadcast()`` (scheduled into the asyncio loop) which pushes
the message into every subscriber queue. Disconnected subscribers are
removed lazily on the next failed put.
"""
from __future__ import annotations

import asyncio


class EventDispatcher:
    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue] = set()

    def subscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.add(queue)

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)

    async def broadcast(self, msg: dict) -> None:
        # Snapshot the set so concurrent unsubscribes don't break iteration.
        for q in list(self.subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                # A slow subscriber that can't keep up — drop them rather than
                # stall the listener. They'll reconnect with a fresh queue.
                self.subscribers.discard(q)
