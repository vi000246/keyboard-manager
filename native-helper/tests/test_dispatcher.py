import asyncio

import pytest

from native_helper.dispatcher import EventDispatcher


@pytest.mark.asyncio
async def test_broadcast_reaches_all_subscribers():
    d = EventDispatcher()
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()
    d.subscribe(q1)
    d.subscribe(q2)
    await d.broadcast({"type": "down", "key": "j"})
    assert (await q1.get())["key"] == "j"
    assert (await q2.get())["key"] == "j"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    d = EventDispatcher()
    q: asyncio.Queue = asyncio.Queue()
    d.subscribe(q)
    d.unsubscribe(q)
    await d.broadcast({"type": "down", "key": "j"})
    assert q.empty()


@pytest.mark.asyncio
async def test_slow_subscriber_gets_evicted_when_queue_full():
    d = EventDispatcher()
    slow: asyncio.Queue = asyncio.Queue(maxsize=1)
    d.subscribe(slow)
    await d.broadcast({"type": "down", "key": "a"})  # fills queue
    await d.broadcast({"type": "down", "key": "b"})  # would block — evict
    assert slow not in d.subscribers


@pytest.mark.asyncio
async def test_broadcast_with_no_subscribers_is_noop():
    d = EventDispatcher()
    await d.broadcast({"type": "down", "key": "x"})  # must not raise
