"""Tests for LitellmTransport."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLitellmTransport:
    def test_init_loads_dotenv_and_imports(self) -> None:
        """Constructor initializes without errors."""
        mock_completion = MagicMock()
        mock_acompletion = MagicMock()

        with patch("app.infrastructure.providers.transports.litellm_sdk.load_dotenv_files") as mock_load:
            with patch("app.infrastructure.providers.transports.litellm_sdk.build_extra_body", return_value={}):
                # Mock the litellm imports inside __init__
                mock_litellm = MagicMock()
                mock_litellm.completion = mock_completion
                mock_litellm.acompletion = mock_acompletion
                with patch.dict("sys.modules", {"litellm": mock_litellm}):
                    from app.infrastructure.providers.transports.litellm_sdk import LitellmTransport
                    transport = LitellmTransport("gpt-4o-mini")
                    assert transport._model == "gpt-4o-mini"
                    mock_load.assert_called_once()

    def test_completion_kwargs_basic(self) -> None:
        """_completion_kwargs produces correct dict."""
        mock_completion = MagicMock()
        mock_acompletion = MagicMock()

        with patch("app.infrastructure.providers.transports.litellm_sdk.load_dotenv_files"):
            with patch("app.infrastructure.providers.transports.litellm_sdk.build_extra_body", return_value={}):
                mock_litellm = MagicMock()
                mock_litellm.completion = mock_completion
                mock_litellm.acompletion = mock_acompletion
                with patch.dict("sys.modules", {"litellm": mock_litellm}):
                    from app.infrastructure.providers.transports.litellm_sdk import LitellmTransport
                    transport = LitellmTransport("gpt-4o-mini")
                    kwargs = transport._completion_kwargs(
                        messages=[{"role": "user", "content": "hi"}],
                        temperature=0.7,
                        max_tokens=100,
                    )
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 100
        assert "extra_body" not in kwargs  # empty extra_body not included

    def test_completion_kwargs_with_extra_body(self) -> None:
        """_completion_kwargs includes extra_body when non-empty."""
        with patch("app.infrastructure.providers.transports.litellm_sdk.load_dotenv_files"):
            with patch(
                "app.infrastructure.providers.transports.litellm_sdk.build_extra_body",
                return_value={"thinking": "enabled"},
            ):
                mock_litellm = MagicMock()
                mock_litellm.completion = MagicMock()
                mock_litellm.acompletion = MagicMock()
                with patch.dict("sys.modules", {"litellm": mock_litellm}):
                    from app.infrastructure.providers.transports.litellm_sdk import LitellmTransport
                    transport = LitellmTransport("claude-sonnet-4")
                    kwargs = transport._completion_kwargs(
                        messages=[{"role": "user", "content": "hi"}],
                        temperature=0.5,
                        max_tokens=200,
                    )
        assert kwargs["extra_body"] == {"thinking": "enabled"}

    def test_complete(self) -> None:
        """complete() calls sync completion and extracts content."""
        mock_completion = MagicMock()
        mock_response = MagicMock()
        mock_completion.return_value = mock_response

        with patch("app.infrastructure.providers.transports.litellm_sdk.load_dotenv_files"):
            with patch("app.infrastructure.providers.transports.litellm_sdk.build_extra_body", return_value={}):
                mock_litellm = MagicMock()
                mock_litellm.completion = mock_completion
                mock_litellm.acompletion = MagicMock()
                with patch.dict("sys.modules", {"litellm": mock_litellm}):
                    with patch("app.infrastructure.providers.transports.litellm_sdk.scale_max_tokens", return_value=100):
                        with patch(
                            "app.infrastructure.providers.transports.litellm_sdk.extract_content",
                            return_value="Hello!",
                        ):
                            from app.infrastructure.providers.transports.litellm_sdk import LitellmTransport
                            transport = LitellmTransport("gpt-4o-mini")
                            result = transport.complete(
                                messages=[{"role": "user", "content": "hi"}],
                                temperature=0.7,
                                max_tokens=100,
                            )
        assert result == "Hello!"
        mock_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_acomplete(self) -> None:
        """acomplete() calls async completion and extracts content."""
        mock_acompletion = AsyncMock()
        mock_response = MagicMock()
        mock_acompletion.return_value = mock_response

        with patch("app.infrastructure.providers.transports.litellm_sdk.load_dotenv_files"):
            with patch("app.infrastructure.providers.transports.litellm_sdk.build_extra_body", return_value={}):
                mock_litellm = MagicMock()
                mock_litellm.completion = MagicMock()
                mock_litellm.acompletion = mock_acompletion
                with patch.dict("sys.modules", {"litellm": mock_litellm}):
                    with patch("app.infrastructure.providers.transports.litellm_sdk.scale_max_tokens", return_value=100):
                        with patch(
                            "app.infrastructure.providers.transports.litellm_sdk.extract_content",
                            return_value="Bonjour!",
                        ):
                            from app.infrastructure.providers.transports.litellm_sdk import LitellmTransport
                            transport = LitellmTransport("gpt-4o-mini")
                            result = await transport.acomplete(
                                messages=[{"role": "user", "content": "bonjour"}],
                                temperature=0.5,
                                max_tokens=100,
                            )
        assert result == "Bonjour!"
        mock_acompletion.assert_called_once()

    def test_with_reasoning_task(self) -> None:
        """Transport can be initialized with a reasoning task."""
        from app.infrastructure.providers.reasoning_models import ReasoningTask

        with patch("app.infrastructure.providers.transports.litellm_sdk.load_dotenv_files"):
            with patch(
                "app.infrastructure.providers.transports.litellm_sdk.build_extra_body",
                return_value={"reasoning": "high"},
            ):
                mock_litellm = MagicMock()
                mock_litellm.completion = MagicMock()
                mock_litellm.acompletion = MagicMock()
                with patch.dict("sys.modules", {"litellm": mock_litellm}):
                    from app.infrastructure.providers.transports.litellm_sdk import LitellmTransport
                    transport = LitellmTransport("deepseek-v4", task=ReasoningTask.JUDGE)
        assert transport._task == ReasoningTask.JUDGE
        assert transport._extra_body == {"reasoning": "high"}
