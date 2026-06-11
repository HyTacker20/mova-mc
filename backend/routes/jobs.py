"""Job management: create, stream events, cancel, status."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.application.job import JobRegistry, TranslationJob
from app.core.mod_scanner import ModScanner
from app.core.settings import Settings
from backend.dev_progress_log import attach_dev_progress_logger
from backend.job_bridge import SseBridge
from backend.schemas import JobCreatedResponse, JobRequest, JobStatusResponse
from backend.sse import serialise_stats, sse_frame, sse_keepalive

router = APIRouter()

job_registry = JobRegistry()
_bridges: dict[str, SseBridge] = {}
_background_tasks: set[asyncio.Task[None]] = set()


@router.post("/jobs", response_model=JobCreatedResponse, status_code=201)
async def create_job(req: JobRequest) -> JobCreatedResponse:
    """Create and immediately start a translation job."""
    settings = Settings(config_data=req.to_settings_dict())

    try:
        scanner = ModScanner(settings.mods_path)
        all_mods = scanner.discover_mods()
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Cannot scan mods: {exc}") from exc

    if req.selected_mods:
        selected_set = set(req.selected_mods)
        for m in all_mods:
            m.selected = m.name in selected_set
    selected = [m for m in all_mods if m.selected]

    if not selected:
        raise HTTPException(status_code=422, detail="No mods selected")

    job = TranslationJob(settings=settings, selected_mods=selected)

    loop = asyncio.get_event_loop()
    bridge = SseBridge(loop)
    job.reporter.subscribe(bridge.on_event)

    if os.environ.get("MOVAMC_DEV") == "1":
        attach_dev_progress_logger(job.reporter)

    job_registry.register(job)
    _bridges[job.id] = bridge

    async def _run_and_close() -> None:
        try:
            await job.run()
        finally:
            # Flush progress events scheduled from worker-thread stages.
            await asyncio.sleep(0)
            bridge.close()

    task = asyncio.create_task(_run_and_close(), name=f"job-{job.id[:8]}")
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return JobCreatedResponse(job_id=job.id, status=job.status.value)


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    """SSE stream of ProgressReporter events for *job_id*."""
    bridge = _bridges.get(job_id)
    if bridge is None:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = bridge.subscribe()

    async def event_stream() -> Any:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=25)
                except asyncio.TimeoutError:
                    yield sse_keepalive()
                    continue
                if frame is None:
                    break
                yield sse_frame(frame)
        except asyncio.CancelledError:
            pass
        finally:
            bridge.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/jobs/{job_id}/cancel", status_code=204)
async def cancel_job(job_id: str) -> None:
    """Request cancellation of a running job."""
    job = job_registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job.cancel()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    """Return current status and (if done) stats for *job_id*."""
    job = job_registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    stats = serialise_stats(job.result) if job.result is not None else None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        error=job.error,
        stats=stats,
    )
