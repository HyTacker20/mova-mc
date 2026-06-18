from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.providers.registry import check_provider_available
from app.infrastructure.providers.transports.anthropic_compat import (
    AnthropicCompatTransport,
    extract_anthropic_text,
    split_anthropic_messages,
)
from app.infrastructure.providers.transports.opencode import (
    OPENCODE_ANTHROPIC_MODELS,
    normalize_opencode_model,
    uses_anthropic_endpoint,
)
from app.infrastructure.providers.reasoning_models import scale_max_tokens


class TestNormalizeOpencodeModel:
    def test_strips_prefix(self):
        assert normalize_opencode_model("opencode-go/kimi-k2.6") == "kimi-k2.6"

    def test_strips_prefix_case_insensitive(self):
        assert normalize_opencode_model("OpenCode-Go/deepseek-v4-flash") == "deepseek-v4-flash"

    def test_passthrough_without_prefix(self):
        assert normalize_opencode_model("glm-5.1") == "glm-5.1"

    def test_strips_openrouter_provider_prefix(self):
        assert normalize_opencode_model("deepseek/deepseek-v4-pro") == "deepseek-v4-pro"

    def test_strips_both_opencode_and_provider_prefix(self):
        assert normalize_opencode_model("opencode-go/deepseek/deepseek-v4-pro") == "deepseek-v4-pro"


class TestUsesAnthropicEndpoint:
    @pytest.mark.parametrize("model", sorted(OPENCODE_ANTHROPIC_MODELS))
    def test_anthropic_models(self, model: str):
        assert uses_anthropic_endpoint(model) is True

    @pytest.mark.parametrize("model", ["deepseek-v4-flash", "kimi-k2.6", "glm-5"])
    def test_openai_models(self, model: str):
        assert uses_anthropic_endpoint(model) is False


class TestScaleOpencodeMaxTokens:
    def test_deepseek_unchanged_when_thinking_disabled(self):
        assert scale_max_tokens("deepseek-v4-pro", 1024) == 1024

    def test_glm_bumped_for_reasoning(self):
        assert scale_max_tokens("glm-5.1", 1024) == 8192

    def test_fast_model_unchanged(self):
        assert scale_max_tokens("mimo-v2.5", 1000) == 1000


class TestSplitAnthropicMessages:
    def test_splits_system_and_user(self):
        system, conversation = split_anthropic_messages(
            [
                {"role": "system", "content": "You are a translator."},
                {"role": "user", "content": "Translate: hello"},
            ]
        )
        assert system == "You are a translator."
        assert conversation == [{"role": "user", "content": "Translate: hello"}]

    def test_no_system(self):
        system, conversation = split_anthropic_messages(
            [
                {"role": "user", "content": "hello"},
            ]
        )
        assert system is None
        assert conversation == [{"role": "user", "content": "hello"}]


class TestExtractAnthropicText:
    def test_extracts_text_block(self):
        data = {"content": [{"type": "text", "text": "  привіт  "}]}
        assert extract_anthropic_text(data, transport="test") == "привіт"

    def test_empty_content(self):
        assert extract_anthropic_text({"content": []}, transport="test") == ""


class TestOpenCodeTransportRouting:
    @patch("app.infrastructure.providers.transports.opencode.OpenAICompatTransport")
    @patch("app.infrastructure.providers.transports.opencode.AnthropicCompatTransport")
    def test_routes_openai_model(self, mock_anthropic: MagicMock, mock_openai: MagicMock):
        from app.infrastructure.providers.transports.opencode import OpenCodeTransport

        OpenCodeTransport(model="deepseek-v4-flash", api_key="test-key")
        mock_openai.assert_called_once()
        mock_anthropic.assert_not_called()
        assert mock_openai.call_args.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    @patch("app.infrastructure.providers.transports.opencode.OpenAICompatTransport")
    @patch("app.infrastructure.providers.transports.opencode.AnthropicCompatTransport")
    def test_scales_max_tokens_for_reasoning_model(self, mock_anthropic: MagicMock, mock_openai: MagicMock):
        from app.infrastructure.providers.transports.opencode import OpenCodeTransport

        mock_inner = MagicMock()
        mock_inner.complete.return_value = "ok"
        mock_openai.return_value = mock_inner

        transport = OpenCodeTransport(model="glm-5.1", api_key="test-key")
        transport.complete([{"role": "user", "content": "hi"}], temperature=0.3, max_tokens=1024)
        mock_inner.complete.assert_called_once_with(
            [{"role": "user", "content": "hi"}],
            0.3,
            8192,
        )

    @patch("app.infrastructure.providers.transports.opencode.OpenAICompatTransport")
    @patch("app.infrastructure.providers.transports.opencode.AnthropicCompatTransport")
    def test_routes_anthropic_model(self, mock_anthropic: MagicMock, mock_openai: MagicMock):
        from app.infrastructure.providers.transports.opencode import OpenCodeTransport

        OpenCodeTransport(model="minimax-m2.5", api_key="test-key")
        mock_anthropic.assert_called_once()
        mock_openai.assert_not_called()

    @patch("app.infrastructure.providers.transports.opencode.OpenAICompatTransport")
    @patch("app.infrastructure.providers.transports.opencode.AnthropicCompatTransport")
    def test_normalizes_prefixed_model(self, mock_anthropic: MagicMock, mock_openai: MagicMock):
        from app.infrastructure.providers.transports.opencode import OpenCodeTransport

        OpenCodeTransport(model="opencode-go/minimax-m3", api_key="test-key")
        mock_anthropic.assert_called_once()
        assert mock_anthropic.call_args.kwargs["model"] == "minimax-m3"


class TestAnthropicCompatTransport:
    def test_complete_posts_to_messages_endpoint(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "translated"}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        transport = AnthropicCompatTransport(
            model="minimax-m2.5",
            base_url="https://opencode.ai/zen/go/v1",
            api_key="test-key",
        )

        with patch("app.infrastructure.providers.transports.anthropic_compat.httpx.Client", return_value=mock_client):
            result = transport.complete(
                [
                    {"role": "system", "content": "Translate."},
                    {"role": "user", "content": "hello"},
                ],
                temperature=0.3,
                max_tokens=100,
            )

        assert result == "translated"
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.args[0] == "https://opencode.ai/zen/go/v1/messages"
        payload = call_kwargs.kwargs["json"]
        assert payload["system"] == "Translate."
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        assert payload["model"] == "minimax-m2.5"


class TestOpencodeProviderAvailable:
    def test_available_with_key(self):
        with (
            patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "go-test-key"}),
            patch("app.infrastructure.providers.registry._try_load_dotenv"),
        ):
            available, msg = check_provider_available("opencode")
        assert available is True
        assert "deepseek-v4-flash" in msg

    def test_unavailable_no_key(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("app.infrastructure.providers.registry._try_load_dotenv"),
        ):
            if "OPENCODE_GO_API_KEY" in os.environ:
                del os.environ["OPENCODE_GO_API_KEY"]
            available, msg = check_provider_available("opencode")
        assert available is False
        assert "OPENCODE_GO_API_KEY" in msg
