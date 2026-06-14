from unittest.mock import MagicMock

import pytest

from app.exceptions import TranslationServiceError
from app.infrastructure.providers.openai_like import OpenAILikeProvider


def _mock_translate_fn(text: str) -> str:
    if text == "fail":
        raise RuntimeError("API error")
    return f"ai_{text}"


class TestOpenAICompatProvider:
    def test_init_with_transport(self):
        transport = MagicMock()
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="uk",
            transport=transport,
            service_name="openaicompatible",
            capitalize=False,
            max_retries=0,
            chunk_size=10,
        )
        assert provider.source_lang == "en"
        assert provider.target_lang == "uk"
        assert provider._CHUNK_SIZE == 10

    def test_translate_whitespace_only(self):
        transport = MagicMock()
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="uk",
            transport=transport,
            capitalize=False,
            max_retries=0,
        )
        result = provider.translate("   ")
        assert result == "   "

    def test_translate_error_raises(self):
        transport = MagicMock()
        transport.complete.side_effect = Exception("API error")
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="uk",
            transport=transport,
            capitalize=False,
            max_retries=0,
        )
        with pytest.raises(TranslationServiceError):
            provider.translate("Hello")

    def test_translate_with_capitalize(self):
        transport = MagicMock()
        transport.complete.return_value = "hola"
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="es",
            transport=transport,
            capitalize=True,
            max_retries=0,
        )
        result = provider.translate("Hello")
        assert result == "Hola"
