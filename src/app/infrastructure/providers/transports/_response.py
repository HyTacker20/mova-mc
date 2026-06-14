"""Shared extraction of assistant text from OpenAI-style chat completions.

All transports return ``completion.choices[0].message.content``.  Doing this
inline (``... or ""``) silently turns a diagnosable failure — e.g. a reasoning
model spending its whole ``max_tokens`` budget on thinking — into an opaque
"Empty response".  :func:`extract_content` centralises the extraction and logs
*why* the content is empty so the cause is visible in the logs.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ..reasoning_models import strip_thinking_artifacts


def _reasoning_tokens(completion: Any) -> int | None:
    """Best-effort read of reasoning-token usage (None if unavailable)."""
    usage = getattr(completion, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    return getattr(details, "reasoning_tokens", None)


def extract_content(completion: Any, *, transport: str) -> str:
    """Return the assistant text, stripped of chain-of-thought blocks.

    When the result is empty, emit a warning explaining the likely cause
    (token-cap exhaustion vs. a reasoning model whose answer never reached the
    ``content`` field) with an actionable hint, instead of returning ``""``
    silently.
    """
    try:
        choice = completion.choices[0]
    except (AttributeError, IndexError, TypeError):
        logger.warning("[{}] malformed completion: no choices to read", transport)
        return ""

    message = getattr(choice, "message", None)
    content = (getattr(message, "content", None) or "").strip()
    content = strip_thinking_artifacts(content)

    if content:
        return content

    finish = getattr(choice, "finish_reason", None)
    reasoning = _reasoning_tokens(completion)
    if finish == "length":
        logger.warning(
            "[{}] empty content: finish_reason=length, reasoning_tokens={}. The model "
            "hit its max_tokens cap — likely a reasoning model that spent the entire "
            "budget on thinking. Increase max_tokens or switch to a non-reasoning model.",
            transport,
            reasoning,
        )
    elif getattr(message, "reasoning_content", None):
        logger.warning(
            "[{}] empty content but reasoning_content is present (finish_reason={}). "
            "This is a reasoning model; the answer never materialised in 'content'. "
            "Use a non-reasoning model for translation.",
            transport,
            finish,
        )
    else:
        logger.warning("[{}] empty content (finish_reason={}, reasoning_tokens={}).", transport, finish, reasoning)
    return content
