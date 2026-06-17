"""Tests for web-mode logging: console init, dev progress bridge, SSE sink."""

from __future__ import annotations

import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from loguru import logger

from app.logging_config import get_console_handler_id, is_logging_configured
from app.utils.progress import ProgressReporter
from backend.app import create_app
from backend.dev_progress_log import attach_dev_progress_logger
from backend.routes import logs as logs_route


class TestWebLoggingStartup:
    def test_create_app_startup_enables_console_sink(self) -> None:
        app = create_app(dev=True)
        with TestClient(app) as client:
            client.get("/api/catalog/providers")

        assert is_logging_configured()
        assert get_console_handler_id() is not None


class TestDevProgressLogger:
    def test_mod_complete_emits_info_log(self) -> None:
        reporter = ProgressReporter()
        attach_dev_progress_logger(reporter)

        captured: list[str] = []

        def _capture(message: str) -> None:
            captured.append(message.strip())

        sink_id = logger.add(_capture, level="INFO", format="{message}")
        try:
            reporter.report_mod_complete("test-mod.jar", translated=5, total=5, failed=0)
        finally:
            logger.remove(sink_id)

        assert any("✓ test-mod.jar" in line and "5/5" in line for line in captured)

    def test_translated_entry_emits_arrow_line(self) -> None:
        reporter = ProgressReporter()
        attach_dev_progress_logger(reporter)

        captured: list[str] = []

        def _capture(message: str) -> None:
            captured.append(message.strip())

        sink_id = logger.add(_capture, level="INFO", format="{message}")
        try:
            reporter.report_translated_entry("key", "Hello", "Привіт")
        finally:
            logger.remove(sink_id)

        assert any("Hello" in line and "Привіт" in line for line in captured)


@pytest.mark.asyncio
async def test_log_sink_threadsafe_enqueue() -> None:
    logs_route.detach_log_sink()
    logs_route._log_history.clear()
    while not logs_route._log_queue.empty():
        logs_route._log_queue.get_nowait()

    logs_route.attach_log_sink()

    def worker() -> None:
        logger.info("thread-safe log line")

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    for _ in range(30):
        await asyncio.sleep(0)
        if any("thread-safe log line" in entry["text"] for entry in logs_route._log_history):
            break

    assert any("thread-safe log line" in entry["text"] for entry in logs_route._log_history)


@pytest.mark.asyncio
async def test_log_sink_drops_oldest_on_queue_full() -> None:
    logs_route.detach_log_sink()
    logs_route._log_history.clear()
    while not logs_route._log_queue.empty():
        logs_route._log_queue.get_nowait()

    logs_route.attach_log_sink()

    # Push more entries than the queue can hold (512 + 4).
    for i in range(516):
        logs_route._enqueue({"text": f"line-{i}"})

    queued_texts = []
    while not logs_route._log_queue.empty():
        queued_texts.append(logs_route._log_queue.get_nowait()["text"])

    assert len(queued_texts) == 512
    assert queued_texts[0] == "line-4"
    assert queued_texts[-1] == "line-515"
