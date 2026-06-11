"""Tests for SSE progress bridge."""

from __future__ import annotations

import asyncio
import threading

import pytest

from backend.job_bridge import SseBridge


@pytest.mark.asyncio
async def test_same_loop_delivers_immediately() -> None:
    loop = asyncio.get_running_loop()
    bridge = SseBridge(loop)
    q = bridge.subscribe()

    bridge.on_event("title", text="Translating...")
    frame = q.get_nowait()

    assert frame is not None
    assert frame["event"] == "title"
    assert frame["data"]["text"] == "Translating..."


@pytest.mark.asyncio
async def test_subscribe_replays_history() -> None:
    loop = asyncio.get_running_loop()
    bridge = SseBridge(loop)

    bridge.on_event("translated_entry", key="k1", source="Hi", translated="Привіт")
    q = bridge.subscribe()

    frame = q.get_nowait()
    assert frame is not None
    assert frame["event"] == "translated_entry"
    assert frame["data"]["source"] == "Hi"


@pytest.mark.asyncio
async def test_worker_thread_uses_threadsafe_dispatch() -> None:
    loop = asyncio.get_running_loop()
    bridge = SseBridge(loop)
    q = bridge.subscribe()
    seen: list[str] = []

    def worker() -> None:
        bridge.on_event("mod_complete", mod_name="a.jar", translated=1, total=1, failed=0)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    for _ in range(20):
        await asyncio.sleep(0)
        while not q.empty():
            frame = q.get_nowait()
            if frame is not None:
                seen.append(str(frame["event"]))
        if seen:
            break

    assert seen == ["mod_complete"]
