"""Contract tests for reasoning-aware transport request shaping."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.providers.reasoning_models import ReasoningTask
from app.infrastructure.providers.transports.opencode import OpenCodeTransport


class TestOpenCodeDeepSeekThinkingContract:
    @patch("app.infrastructure.providers.transports.opencode.OpenAICompatTransport")
    @patch("app.infrastructure.providers.transports.opencode.AnthropicCompatTransport")
    def test_translate_sends_thinking_disabled(
        self,
        mock_anthropic: MagicMock,
        mock_openai: MagicMock,
    ) -> None:
        OpenCodeTransport(model="deepseek-v4-flash", api_key="test-key")
        mock_openai.assert_called_once()
        assert mock_openai.call_args.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    @patch("app.infrastructure.providers.transports.opencode.OpenAICompatTransport")
    @patch("app.infrastructure.providers.transports.opencode.AnthropicCompatTransport")
    def test_judge_task_still_disables_thinking_for_deepseek(
        self,
        mock_anthropic: MagicMock,
        mock_openai: MagicMock,
    ) -> None:
        OpenCodeTransport(model="deepseek-v4-flash", api_key="test-key", task=ReasoningTask.JUDGE)
        assert mock_openai.call_args.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.opencode_live
class TestOpenCodeLiveProbe:
    """Opt-in live probe: ``pytest -m opencode_live`` with ``OPENCODE_GO_API_KEY`` set."""

    @pytest.fixture(autouse=True)
    def _require_key(self) -> None:
        if not os.getenv("OPENCODE_GO_API_KEY"):
            pytest.skip("OPENCODE_GO_API_KEY not set")

    def test_deepseek_flash_returns_content_with_thinking_disabled(self) -> None:
        transport = OpenCodeTransport(model="deepseek-v4-flash", task=ReasoningTask.JUDGE)
        result = transport.complete(
            [{"role": "user", "content": "Reply with exactly: OK"}],
            temperature=0.0,
            max_tokens=64,
        )
        assert result.strip()
