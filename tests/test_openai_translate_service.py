from unittest.mock import MagicMock

import pytest

from app.domain.models import TranslationUnit
from app.exceptions import TranslationServiceError
from app.infrastructure.providers.openai_like import OpenAILikeProvider

def _mock_translate_fn(text: str) -> str:
    if text == "fail":
        raise RuntimeError("API error")
    return f"ai_{text}"

def _make_provider(capitalize: bool = False, chunk_size: int = 0) -> OpenAILikeProvider:
    transport = MagicMock()
    transport.complete.side_effect = lambda messages, **_: _mock_translate_fn(
        messages[-1]["content"].replace("Translate: ", "")
    )
    return OpenAILikeProvider(
        source_lang="en",
        target_lang="uk",
        transport=transport,
        service_name="test",
        capitalize=capitalize,
        max_retries=0,
        chunk_size=chunk_size,
    )

class TestOpenAILikeProvider:
    def test_init_with_transport(self):
        transport = MagicMock()
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="uk",
            transport=transport,
            capitalize=False,
            max_retries=0,
        )
        assert provider.source_lang == "en"
        assert provider.target_lang == "uk"
        assert provider.capitalize is False

    def test_translate_whitespace_only(self):
        provider = _make_provider(capitalize=False)
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

    def test_translate_unit_failure(self):
        transport = MagicMock()
        transport.complete.side_effect = Exception("API error")
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="uk",
            transport=transport,
            capitalize=False,
            max_retries=0,
        )
        unit = TranslationUnit(key="k1", source_text="Hello", file_type="json")
        result = provider.translate_unit(unit)
        assert result.unit == unit
        assert result.translated_text == "Hello"
        assert result.success is False
        assert result.error == "API error"

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

    def test_chunk_translate_error_returns_originals(self):
        transport = MagicMock()
        transport.complete.side_effect = RuntimeError("API down")
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="uk",
            transport=transport,
            capitalize=False,
            max_retries=0,
            chunk_size=2,
        )
        result = provider._translate_chunk([("k1", "hello"), ("k2", "world")])
        assert result == {"k1": "hello", "k2": "world"}

    def test_translate_empty_string(self):
        provider = _make_provider()
        assert provider.translate("") == ""
