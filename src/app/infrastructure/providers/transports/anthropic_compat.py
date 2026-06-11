"""Anthropic-compatible transport — for /v1/messages APIs (sync + async via httpx)."""

from __future__ import annotations

from typing import Any

try:
    import httpx

    HAS_HTTPX = True
except ImportError:  # pragma: no cover
    HAS_HTTPX = False

_ANTHROPIC_VERSION = "2023-06-01"


def split_anthropic_messages(
    messages: list[dict[str, str]],
) -> tuple[str | None, list[dict[str, str]]]:
    """Split OpenAI-style messages into Anthropic system + conversation messages."""
    system_parts: list[str] = []
    conversation: list[dict[str, str]] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            if content:
                system_parts.append(content)
        elif role in ("user", "assistant"):
            conversation.append({"role": role, "content": content})
    system = "\n\n".join(system_parts) if system_parts else None
    return system, conversation


def extract_anthropic_text(data: dict[str, Any], *, transport: str) -> str:
    """Return assistant text from an Anthropic Messages API response."""
    from loguru import logger

    content_blocks = data.get("content") or []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text = (block.get("text") or "").strip()
            if text:
                return text
    stop_reason = data.get("stop_reason")
    logger.warning("[{}] empty content (stop_reason={}).", transport, stop_reason)
    return ""


class AnthropicCompatTransport:
    """POST to {base_url}/messages with Anthropic request/response format."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx is required for Anthropic-compatible transport")
        if not api_key:
            raise ValueError("API key is required for Anthropic-compatible transport.")
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        system, conversation = split_anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": conversation,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        return payload

    def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        payload = self._build_payload(messages, temperature, max_tokens)
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/messages",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return extract_anthropic_text(resp.json(), transport=type(self).__name__)

    async def acomplete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        payload = self._build_payload(messages, temperature, max_tokens)
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._base_url}/messages",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return extract_anthropic_text(resp.json(), transport=type(self).__name__)
