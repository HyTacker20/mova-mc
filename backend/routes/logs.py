"""SSE endpoint that streams loguru log messages to the browser."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import deque
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from loguru import logger
from starlette.requests import Request
from starlette.responses import StreamingResponse

router = APIRouter()

# Queue fed by the loguru sink; up to 256 backlogged messages.
_log_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
_log_history: deque[dict] = deque(maxlen=500)
_loop: asyncio.AbstractEventLoop | None = None


def _enqueue(entry: dict) -> None:
    """Append to history and push to the SSE queue (event-loop thread only)."""
    _log_history.append(entry)
    try:
        _log_queue.put_nowait(entry)
    except asyncio.QueueFull:
        try:
            _log_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        with contextlib.suppress(asyncio.QueueFull):
            _log_queue.put_nowait(entry)


def _loguru_sink(message: object) -> None:
    """Non-blocking enqueue for the loguru callback sink."""
    record = message.record  # type: ignore[union-attr]
    text_body = str(record["message"]).strip()
    if not text_body:
        return
    level = record["level"].name
    time_str = record["time"].strftime("%H:%M:%S")
    text = f"{level}: {time_str} | {text_body}"
    entry = {"text": text, "level": level}
    if _loop is None:
        _enqueue(entry)
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is _loop:
        _enqueue(entry)
    else:
        _loop.call_soon_threadsafe(_enqueue, entry)


_LOG_SINK_ID: int | None = None


def attach_log_sink() -> None:
    """Route loguru INFO+ messages to the SSE queue."""
    global _LOG_SINK_ID, _loop
    if _LOG_SINK_ID is not None:
        return
    _loop = asyncio.get_running_loop()
    _LOG_SINK_ID = logger.add(_loguru_sink, level="INFO")


def detach_log_sink() -> None:
    """Remove the loguru→SSE sink."""
    global _LOG_SINK_ID, _loop
    if _LOG_SINK_ID is not None:
        logger.remove(_LOG_SINK_ID)
        _LOG_SINK_ID = None
    _loop = None


async def _event_stream() -> AsyncGenerator[str, None]:
    """Yield new log lines as SSE events."""
    for entry in list(_log_history):
        yield f"data: {json.dumps(entry)}\n\n"
    while True:
        try:
            entry = await asyncio.wait_for(_log_queue.get(), timeout=25.0)
            yield f"data: {json.dumps(entry)}\n\n"
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"


@router.get("/logs/stream")
async def stream_logs(request: Request) -> StreamingResponse:
    """SSE stream of backend log messages.

    Connect with ``new EventSource('/api/logs/stream')``.
    """
    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
