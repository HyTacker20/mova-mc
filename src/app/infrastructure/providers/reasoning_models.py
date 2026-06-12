"""Per-model reasoning/thinking policy for LLM transports.

DeepSeek V4 supports ``extra_body.thinking.type = disabled``; Kimi rejects
simultaneous ``thinking`` + ``reasoning_effort``.  GLM/MiMo need a larger
``max_tokens`` budget when thinking cannot be turned off.
"""

from __future__ import annotations

import re
from enum import Enum

# ── Model family detection ───────────────────────────────────────────────

_DEEPSEEK_V4_RE = re.compile(r"deepseek[-_]?v4", re.IGNORECASE)
_KIMI_K2_RE = re.compile(r"kimi[-_]?k2", re.IGNORECASE)
_GLM_RE = re.compile(r"glm[-_]?", re.IGNORECASE)
_MIMO_RE = re.compile(r"mimo[-_]?v", re.IGNORECASE)

DEEPSEEK_V4_MODELS: frozenset[str] = frozenset({
    "deepseek-v4-pro",
    "deepseek-v4-flash",
})

KIMI_K2_MODELS: frozenset[str] = frozenset({
    "kimi-k2.5",
    "kimi-k2.6",
})

# Models that may spend output budget on internal reasoning when thinking
# cannot be disabled via the API.
REASONING_TOKEN_BUMP_MODELS: frozenset[str] = frozenset({
    "glm-5.1",
    "glm-5",
    "kimi-k2.5",
    "kimi-k2.6",
})

_MIN_REASONING_TOKENS = 8192

# ── Think-tag stripping ──────────────────────────────────────────────────

_THINK_OPEN = "\x3cthink\x3e"
_THINK_CLOSE = "\x3c/think\x3e"

_THINK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE),
    re.compile(
        re.escape(_THINK_OPEN) + r".*?" + re.escape(_THINK_CLOSE) + r"\s*",
        re.DOTALL | re.IGNORECASE,
    ),
    re.compile(r"<THINK>.*?</THINK>\s*", re.DOTALL),
)


class ReasoningTask(Enum):
    """How the model is being used (policy is per-model, not per-task for DeepSeek)."""

    TRANSLATE = "translate"
    JUDGE = "judge"
    CORRECTOR = "corrector"


def normalize_model_id(model: str) -> str:
    """Return bare model id without provider prefixes."""
    normalized = model.strip()
    if "/" in normalized:
        _, _, bare = normalized.rpartition("/")
        if bare:
            normalized = bare
    prefix = "opencode-go/"
    if normalized.lower().startswith(prefix):
        normalized = normalized[len(prefix) :]
    return normalized


def is_deepseek_v4(model: str) -> bool:
    bare = normalize_model_id(model).lower()
    return bare in DEEPSEEK_V4_MODELS or bool(_DEEPSEEK_V4_RE.search(bare))


def is_kimi_k2(model: str) -> bool:
    bare = normalize_model_id(model).lower()
    return bare in KIMI_K2_MODELS or bool(_KIMI_K2_RE.search(bare))


def is_reasoning_capable_model(model: str) -> bool:
    """Return True when the model may use thinking/reasoning output channels."""
    bare = normalize_model_id(model).lower()
    if is_deepseek_v4(bare) or is_kimi_k2(bare):
        return True
    if bare in REASONING_TOKEN_BUMP_MODELS:
        return True
    return bool(_GLM_RE.search(bare) or _MIMO_RE.search(bare))


def build_extra_body(model: str, *, task: ReasoningTask = ReasoningTask.TRANSLATE) -> dict | None:
    """Return OpenAI ``extra_body`` for thinking control, or None when not applicable.

    DeepSeek V4: always disable thinking (translate, judge, corrector).
    Kimi K2: never combined with top-level ``reasoning_effort`` (HTTP 400).
    """
    _ = task  # per-model policy; task reserved for future per-task overrides
    bare = normalize_model_id(model).lower()

    if is_deepseek_v4(bare):
        return {"thinking": {"type": "disabled"}}

    return None


def allows_reasoning_effort(model: str) -> bool:
    """Return False when sending ``reasoning_effort`` would break the API (Kimi K2)."""
    return not is_kimi_k2(model)


def scale_max_tokens(
    model: str,
    max_tokens: int,
    *,
    task: ReasoningTask = ReasoningTask.TRANSLATE,
) -> int:
    """Raise token budget for models that cannot disable thinking."""
    _ = task
    bare = normalize_model_id(model).lower()

    if is_deepseek_v4(bare):
        return max_tokens

    if bare in REASONING_TOKEN_BUMP_MODELS:
        return max(max_tokens, _MIN_REASONING_TOKENS)

    return max_tokens


def strip_thinking_artifacts(text: str) -> str:
    """Remove inline chain-of-thought blocks from assistant text."""
    result = text
    for pattern in _THINK_PATTERNS:
        result = pattern.sub("", result)
    return result.strip()
