"""OpenCode Go transport — routes models to OpenAI or Anthropic-compatible endpoints."""

from __future__ import annotations

import os

from ....core.dotenv_loader import load_dotenv_files
from .anthropic_compat import AnthropicCompatTransport
from .compat_sdk import OpenAICompatTransport

OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"

OPENCODE_ANTHROPIC_MODELS: frozenset[str] = frozenset({
    "minimax-m3",
    "minimax-m2.7",
    "minimax-m2.5",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-plus",
})

# DeepSeek V4 models enable thinking by default; disable for translation/QA tasks.
OPENCODE_DEEPSEEK_MODELS: frozenset[str] = frozenset({
    "deepseek-v4-pro",
    "deepseek-v4-flash",
})

# Other OpenCode models that may spend output budget on internal reasoning.
OPENCODE_REASONING_MODELS: frozenset[str] = frozenset({
    "glm-5.1",
    "glm-5",
    "kimi-k2.5",
    "kimi-k2.6",
    "mimo-v2.5-pro",
}) | OPENCODE_DEEPSEEK_MODELS

_OPENCODE_MIN_REASONING_TOKENS = 8192


def normalize_opencode_model(model: str) -> str:
    """Normalize a model ID for the OpenCode Go API.

    * Strips the ``opencode-go/`` prefix (used in some config formats).
    * Strips OpenRouter-style provider prefixes (``deepseek/``, ``openai/``, ...)
      that are not valid OpenCode Go model IDs.  If a saved config carries a
      prefixed name from a previous fetch, only the bare model portion is kept.

    Examples::

        >>> normalize_opencode_model("opencode-go/deepseek-v4-pro")
        'deepseek-v4-pro'
        >>> normalize_opencode_model("deepseek/deepseek-v4-pro")
        'deepseek-v4-pro'
        >>> normalize_opencode_model("deepseek-v4-pro")
        'deepseek-v4-pro'
    """
    normalized = model.strip()

    # Strip "opencode-go/" prefix (used in OpenCode config files).
    prefix = "opencode-go/"
    if normalized.lower().startswith(prefix):
        normalized = normalized[len(prefix):]

    # Strip OpenRouter-style provider prefix (e.g. "deepseek/", "openai/").
    # OpenCode Go model IDs never contain slashes -- if there is one,
    # everything before it is a provider prefix that the API will reject.
    if "/" in normalized:
        _, _, bare = normalized.rpartition("/")
        if bare:
            normalized = bare

    return normalized


def uses_anthropic_endpoint(model: str) -> bool:
    """Return True when *model* should use the /v1/messages endpoint."""
    return normalize_opencode_model(model).lower() in OPENCODE_ANTHROPIC_MODELS


def _openai_extra_body(model: str) -> dict | None:
    """Return provider-specific extra_body for OpenAI-compatible OpenCode models."""
    if model.lower() in OPENCODE_DEEPSEEK_MODELS:
        return {"thinking": {"type": "disabled"}}
    return None


def scale_opencode_max_tokens(model: str, max_tokens: int) -> int:
    """Raise token budget for reasoning-capable models when thinking cannot be disabled."""
    normalized = normalize_opencode_model(model).lower()
    if normalized in OPENCODE_DEEPSEEK_MODELS:
        return max_tokens
    if normalized in OPENCODE_REASONING_MODELS:
        return max(max_tokens, _OPENCODE_MIN_REASONING_TOKENS)
    return max_tokens


class OpenCodeTransport:
    """Facade that delegates to OpenAI or Anthropic transport based on model ID."""

    _inner: AnthropicCompatTransport | OpenAICompatTransport

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        load_dotenv_files()
        resolved_key = api_key or os.getenv("OPENCODE_GO_API_KEY") or ""
        if not resolved_key:
            raise ValueError("OPENCODE_GO_API_KEY environment variable not set.")
        resolved_url = base_url or os.getenv("OPENCODE_GO_BASE_URL") or OPENCODE_GO_BASE_URL
        self._model = normalize_opencode_model(model)

        if uses_anthropic_endpoint(self._model):
            self._inner = AnthropicCompatTransport(
                model=self._model,
                base_url=resolved_url,
                api_key=resolved_key,
            )
        else:
            self._inner = OpenAICompatTransport(
                model=self._model,
                base_url=resolved_url,
                api_key=resolved_key,
                extra_body=_openai_extra_body(self._model),
            )

    def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        scaled = scale_opencode_max_tokens(self._model, max_tokens)
        return self._inner.complete(messages, temperature, scaled)

    async def acomplete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        scaled = scale_opencode_max_tokens(self._model, max_tokens)
        return await self._inner.acomplete(messages, temperature, scaled)
