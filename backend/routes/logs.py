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

# Queue fed by the loguru sink; up to 512 backlogged messages.
_log_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=512)
_log_history: deque[dict] = deque(maxlen=5000)
_loop: asyncio.AbstractEventLoop | None = None

# Pinned startup messages that are never evicted from history.
# Appended by the lifespan after config load; replayed before history.
_startup_log: list[dict] = []


def reset_state() -> None:
    """Reset module-level state (for test isolation)."""
    global _log_queue, _log_history, _loop, _startup_log
    _log_queue = asyncio.Queue(maxsize=512)
    _log_history = deque(maxlen=5000)
    _loop = None
    _startup_log = []


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
    record = message.record  # type: ignore[union-attr, attr-defined]
    text_body = str(record["message"]).strip()
    if not text_body:
        return
    level = record["level"].name
    time_str = record["time"].strftime("%H:%M:%S")

    # Determine log category from the logger name for tab filtering.
    logger_name: str = record["name"]
    is_qa = any(
        seg in logger_name
        for seg in (
            ".utils.qa_log",
            ".providers.qa_wrapper",
            ".providers.judge",
            ".stages.validate",
        )
    )
    is_translation = not is_qa and any(
        seg in logger_name
        for seg in (
            ".dev_progress_log",
            ".infrastructure.filesystem",
            ".application.stages.translate",
            ".application.stages.parse",
            ".application.stages.write",
            ".application.stages.discover",
            ".application.stages.unpack",
            ".application.stages.repack",
            ".application.pipeline",
        )
    )

    if is_qa:
        category = "qa"
        if text_body.startswith("QA | "):
            text_body = text_body[5:]
        text = f"{time_str} · {text_body}"
    elif is_translation:
        category = "translation"
        text = f"{level}: {time_str} | {text_body}"
    else:
        category = "general"
        text = f"{level}: {time_str} | {text_body}"

    entry = {"text": text, "level": level, "category": category}
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


def capture_startup_config(
    provider: str,
    model: str,
    source: str,
    target: str,
    output_mode: str,
    cache: str,
    qa: str,
    workers: str,
) -> None:
    """Store startup config as pinned log entries that are never evicted.

    Called from the lifespan after config is loaded.  These entries are
    replayed before the rolling history so the user always sees how the
    server was configured even after a long translation job fills the
    history deque.
    """
    import time as _time

    ts = _time.strftime("%H:%M:%S")
    prefix = f"INFO: {ts} |"

    _startup_log.clear()
    _startup_log.extend(
        [
            {
                "text": f"{prefix} provider={provider}  model={model}",
                "level": "INFO",
                "category": "general",
            },
            {
                "text": f"{prefix} {source} → {target}  "
                f"output={output_mode}  cache={cache}  qa={qa}  workers={workers}",
                "level": "INFO",
                "category": "general",
            },
        ]
    )


async def _event_stream(request: Request) -> AsyncGenerator[str, None]:
    """Yield new log lines as SSE events.

    Replays pinned startup config first, then recent history, then
    streams live entries.  Exits when the client disconnects or the
    connection times out.
    """
    for entry in _startup_log:
        if await request.is_disconnected():
            return
        yield f"data: {json.dumps(entry)}\n\n"
    for entry in list(_log_history):
        if await request.is_disconnected():
            return
        yield f"data: {json.dumps(entry)}\n\n"
    while True:
        if await request.is_disconnected():
            break
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
        _event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
