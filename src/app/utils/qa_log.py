"""Plain-text QA progress lines for the rotating log file."""

from __future__ import annotations

from typing import Any

from loguru import logger

from ..domain.qa_display import (
    format_provider_model,
    format_qa_key,
    format_text_change_preview,
    strip_mc_formatting,
)

# ── Fallback explanations when the judge provides no *why* ──────────
_WHY_FALLBACK: dict[str, str] = {
    "russism": "contains Russian words or surzhyk (mixed Russian/Ukrainian)",
    "grammar": "grammatical error (case, gender, or agreement)",
    "meaning": "mistranslation that changes the intended meaning",
    "terminology": "violates Minecraft mod translation terminology",
    "untranslated": "text left in the wrong language",
    "punctuation": "added or removed trailing punctuation",
    "placeholder": "missing or altered placeholder (%s, %d, §-code)",
}


def _default_why(issue: str) -> str:
    """Return a fallback explanation when the judge provides none."""
    return _WHY_FALLBACK.get(issue, f"translation quality issue: {issue}")


def _src_line(source: str) -> str:
    """Format a source-text preview line (always quoted)."""
    cleaned = strip_mc_formatting(source)
    return f'   src:  "{cleaned}"'


def _tgt_line(translated: str) -> str:
    """Format a translated-text preview line (always quoted)."""
    cleaned = strip_mc_formatting(translated)
    return f'   tgt:  "{cleaned}"'


def _was_line(text: str) -> str:
    """Format a 'before correction' line."""
    cleaned = strip_mc_formatting(text)
    return f'   was:  "{cleaned}"'


def _now_line(text: str) -> str:
    """Format an 'after correction' line."""
    cleaned = strip_mc_formatting(text)
    return f'   now:  "{cleaned}"'


def _why_line(why: str) -> str:
    """Format the judge's explanation line."""
    return f"   why:  {why}"


def _score_line(score: int | None, issue: str | None) -> str | None:
    """Format score/issue summary, or None if neither is available."""
    parts: list[str] = []
    if score is not None:
        parts.append(f"{score}/5")
    if issue:
        parts.append(str(issue))
    if parts:
        return f"   flag: {' · '.join(parts)}"
    return None


def format_qa_event(event: str, **kw: Any) -> str | None:
    """Return a plain-text QA line or multi-line block for *event*, or None if unhandled."""
    if event == "qa_start":
        label = format_provider_model(kw.get("provider", ""), kw.get("model", ""))
        return f"── QA review: {kw.get('total', 0)} entries via {label} ──"

    if event == "qa_verdict":
        if not kw.get("is_flagged"):
            return None
        score = kw.get("score", 0)
        key = format_qa_key(kw.get("key", "?"))
        issue = kw.get("issue")
        source = kw.get("source", "")
        translated = kw.get("translated", "")
        why = kw.get("why", "")

        # Fallback explanation when the judge provides no why
        if not why and issue:
            why = _default_why(str(issue))

        header = f"── ⚠ {key} · {score}/5"
        if issue:
            header += f" · {issue}"
        header += " ──"

        lines = [header]
        if source:
            lines.append(_src_line(source))
        if translated:
            lines.append(_tgt_line(translated))
        if why:
            lines.append(_why_line(why))
        return "\n".join(lines)

    if event == "qa_correction":
        accepted = kw.get("accepted", False)
        attempt = kw.get("attempt", 0)
        max_attempts = kw.get("max_attempts", 1)
        reason = kw.get("reason")
        source = kw.get("source", "")
        original = kw.get("original", "")
        corrected = kw.get("corrected", "")
        why = kw.get("why", "")

        icon = "✓" if accepted else "✗"
        if attempt == 0 and accepted and not reason:
            # Simple judge-fix: suppress — qa_inline_fix follows with full context
            return None

        verb = "accepted" if accepted else ("unchanged" if reason == "unchanged" else "rejected")
        header = f"   ↳ {icon} fix {verb}"
        header += f" · attempt {attempt}/{max_attempts}"
        if reason and reason not in ("unchanged",):
            header += f" — {reason}"

        lines = [header]
        if original and corrected:
            lines.append(f"      {format_text_change_preview(original, corrected)}")
        elif corrected and not accepted:
            lines.append(f'      tried: "{strip_mc_formatting(corrected)}"')
        if why:
            lines.append(f"      why:  {why}")
        return "\n".join(lines)

    if event == "qa_warning":
        key = format_qa_key(kw.get("key", "?")) if kw.get("key") else "judge"
        msg = kw.get("message", "")
        return f"  ⚡ {key}: {msg}"

    if event == "qa_done":
        flagged = kw.get("flagged", 0)
        corrected = kw.get("corrected", 0)
        return f"\n── ✓ QA done: {flagged} flagged, {corrected} corrected ──"

    if event == "qa_inline_status":
        message = kw.get("message")
        if message:
            return str(message)
        provider = kw.get("provider", "")
        model = kw.get("model", "")
        label = format_provider_model(provider, model)
        return f"Inline QA · {label}"

    if event == "qa_inline_judging":
        count = kw.get("count", 0)
        return f"→ judging {count} item(s)…"

    if event == "qa_inline_fix":
        key = format_qa_key(kw.get("key", "?"))
        original = kw.get("original", "")
        fixed = kw.get("fixed", "")
        source = kw.get("source", "")
        score = kw.get("score")
        issue = kw.get("issue")
        why = kw.get("why")

        # Fallback explanation when the judge provides no why
        if not why and issue:
            why = _default_why(str(issue))

        lines = [f"── ✓ {key} · fix applied ──"]
        if source:
            lines.append(_src_line(source))
        if original:
            lines.append(_was_line(original))
        if fixed:
            lines.append(_now_line(fixed))
        sc = _score_line(score, issue)
        if sc:
            lines.append(sc)
        if why:
            lines.append(_why_line(why))
        return "\n".join(lines)

    if event == "qa_inline_summary":
        flagged = kw.get("flagged", 0)
        total = kw.get("total", 0)
        corrected = kw.get("corrected", 0)
        elapsed = kw.get("elapsed", 0.0)
        if flagged == 0 and corrected == 0:
            return None
        return (
            f"← batch · {flagged}/{total} flagged, {corrected} corrected "
            f"({elapsed:.1f}s)"
        )

    if event == "qa_inline_error":
        message = kw.get("message", "")
        elapsed = kw.get("elapsed", 0.0)
        return f"✗ judge error ({elapsed:.1f}s): {message}"

    if event == "qa_inline_note":
        key = kw.get("key", "")
        message = kw.get("message", "")
        if key:
            return f"  ↪ {format_qa_key(str(key))}: {message}"
        return f"  ↪ {message}"

    return None


def log_qa_event(event: str, **kw: Any) -> None:
    """Write a formatted QA progress line to the log file."""
    line = format_qa_event(event, **kw)
    if line is not None:
        logger.info("QA | {}", line)
