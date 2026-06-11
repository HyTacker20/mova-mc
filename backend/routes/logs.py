"""SSE endpoint that streams loguru log messages to the browser."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from loguru import logger
from starlette.requests import Request
from starlette.responses import StreamingResponse

router = APIRouter()

# Queue fed by the loguru sink; up to 256 backlogged messages.
_log_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)


def _loguru_sink(message: str) -> None:
    """Non-blocking enqueue for the loguru callback sink."""
    if not message.strip():
        return
    try:
        _log_queue.put_nowait({"text": message.strip()})
    except asyncio.QueueFull:
        pass  # drop oldest — consumer is too slow


_LOG_SINK_ID: int | None = None


def attach_log_sink() -> None:
    """Route loguru INFO+ messages to the SSE queue."""
    global _LOG_SINK_ID
    if _LOG_SINK_ID is not None:
        return
    _LOG_SINK_ID = logger.add(_loguru_sink, level="INFO", format="{message}")


def detach_log_sink() -> None:
    """Remove the loguru→SSE sink."""
    global _LOG_SINK_ID
    if _LOG_SINK_ID is not None:
        logger.remove(_LOG_SINK_ID)
        _LOG_SINK_ID = None


async def _event_stream() -> AsyncGenerator[str, None]:
    """Yield new log lines as SSE events."""
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
