"""Plain-text QA progress lines for the rotating log file."""

from __future__ import annotations

from typing import Any

from loguru import logger

from ..domain.qa_display import format_provider_model, format_qa_correction_line


def _escape_newlines(text: str) -> str:
    return text.replace("\n", "\\n")


def format_qa_event(event: str, **kw: Any) -> str | None:
    """Return a plain-text QA line for *event*, or None if unhandled."""
    if event == "qa_start":
        label = format_provider_model(kw.get("provider", ""), kw.get("model", ""))
        return f"───── ◆ Reviewing {kw.get('total', 0)} entries via {label} ─────"
    if event == "qa_verdict":
        if not kw.get("is_flagged"):
            return None
        icon = "⚠"
        score = kw.get("score", 0)
        key = kw.get("key", "?")
        issue = kw.get("issue")
        line = f"  {icon} {key}: scored {score}/5"
        if issue:
            line += f" — {issue}"
        return line
    if event == "qa_correction":
        return format_qa_correction_line(
            key=kw.get("key", "?"),
            accepted=kw.get("accepted", False),
            attempt=kw.get("attempt", 0),
            max_attempts=kw.get("max_attempts", 1),
        )
    if event == "qa_warning":
        key = kw.get("key", "?")
        msg = kw.get("message", "")
        return f"  ⚡ {key}: {msg}"
    if event == "qa_done":
        flagged = kw.get("flagged", 0)
        corrected = kw.get("corrected", 0)
        return f"───── ✓ QA complete: {flagged} flagged, {corrected} corrected ─────"
    if event == "qa_inline_status":
        message = kw.get("message")
        if message:
            return str(message)
        provider = kw.get("provider", "")
        model = kw.get("model", "")
        label = format_provider_model(provider, model)
        return f"───── Inline QA active ({label}) ─────"
    if event == "qa_inline_judging":
        count = kw.get("count", 0)
        chunk_size = kw.get("chunk_size", 0)
        return f"→ judging {count} item(s) (chunk={chunk_size})"
    if event == "qa_inline_fix":
        key = kw.get("key", "?")
        orig = _escape_newlines(kw.get("original", ""))
        fixed = _escape_newlines(kw.get("fixed", ""))
        return f"  ✓ {key}: {orig} → {fixed}"
    if event == "qa_inline_summary":
        flagged = kw.get("flagged", 0)
        total = kw.get("total", 0)
        corrected = kw.get("corrected", 0)
        elapsed = kw.get("elapsed", 0.0)
        return (
            f"← {flagged}/{total} flagged, {corrected}/{flagged} corrected "
            f"({elapsed:.1f}s)"
        )
    if event == "qa_inline_error":
        message = kw.get("message", "")
        elapsed = kw.get("elapsed", 0.0)
        return f"✗ judge failed ({elapsed:.1f}s): {message}"
    return None


def log_qa_event(event: str, **kw: Any) -> None:
    """Write a formatted QA progress line to the log file."""
    line = format_qa_event(event, **kw)
    if line is not None:
        logger.info("QA | {}", line)
