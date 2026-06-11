from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.domain.models import TranslationResult, TranslationUnit
from app.exceptions import TranslationServiceError
from app.infrastructure.providers.google import GoogleProvider
from app.infrastructure.providers.openai_like import OpenAILikeProvider

_GOOGLE_PROVIDERS = ["new_google"]

def _make_google_provider(_key: str) -> GoogleProvider:
    return GoogleProvider(source_lang="en", target_lang="es", capitalize=False)

def _make_llm_provider() -> OpenAILikeProvider:
    transport = MagicMock()
    transport.complete.return_value = "texto traducido"
    return OpenAILikeProvider(
        source_lang="en",
        target_lang="es",
        transport=transport,
        service_name="test",
        capitalize=False,
        max_retries=0,
        chunk_size=3,
    )

class TestGoogleProviderContract:
    @pytest.mark.parametrize("provider_key", _GOOGLE_PROVIDERS)
    def test_translate_empty_string(self, provider_key: str):
        p = _make_google_provider(provider_key)
        assert p.translate("") == ""
        assert p.translate("   ") == "   "

    @pytest.mark.parametrize("provider_key", _GOOGLE_PROVIDERS)
    def test_translate_unit_failure_returns_result(self, provider_key: str):
        p = _make_google_provider(provider_key)
        unit = TranslationUnit(key="k1", source_text="hello", file_type="json")
        with patch.object(p, "_translate_text", side_effect=RuntimeError("fail")):
            result = p.translate_unit(unit)
        assert isinstance(result, TranslationResult)
        assert result.unit == unit
        assert result.translated_text == "hello"
        assert result.success is False
        assert result.error == "fail"

class TestLLMProviderContract:
    def test_translate_single(self):
        p = _make_llm_provider()
        result = p.translate("hello")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_translate_empty(self):
        p = _make_llm_provider()
        assert p.translate("") == ""

    def test_translate_capitalize(self):
        transport = MagicMock()
        transport.complete.return_value = "hola mundo"
        p = OpenAILikeProvider(
            source_lang="en",
            target_lang="es",
            transport=transport,
            capitalize=True,
            max_retries=0,
        )
        result = p.translate("hello world")
        assert result == "Hola mundo"

    def test_translate_error_raises(self):
        transport = MagicMock()
        transport.complete.side_effect = RuntimeError("API down")
        p = OpenAILikeProvider(
            source_lang="en",
            target_lang="es",
            transport=transport,
            capitalize=False,
            max_retries=0,
        )
        with pytest.raises(TranslationServiceError):
            p.translate("hello")

    def test_translate_unit_failure_returns_result(self):
        transport = MagicMock()
        transport.complete.side_effect = RuntimeError("API down")
        p = OpenAILikeProvider(
            source_lang="en",
            target_lang="es",
            transport=transport,
            capitalize=False,
            max_retries=0,
        )
        unit = TranslationUnit(key="k1", source_text="hello", file_type="json")
        result = p.translate_unit(unit)
        assert isinstance(result, TranslationResult)
        assert result.unit == unit
        assert result.translated_text == "hello"
        assert result.success is False
        assert result.error == "API down"

    def test_translate_chunk_error_returns_originals(self):
        transport = MagicMock()
        transport.complete.side_effect = RuntimeError("API down")
        p = OpenAILikeProvider(
            source_lang="en",
            target_lang="es",
            transport=transport,
            capitalize=False,
            max_retries=0,
        )
        result = p._translate_chunk([("k1", "hello"), ("k2", "world")])
        assert result == {"k1": "hello", "k2": "world"}

class TestTranslationModelContract:
    def test_translation_unit_creation(self):
        unit = TranslationUnit(key="test.key", source_text="Hello", file_type="json")
        assert unit.key == "test.key"
        assert unit.source_text == "Hello"
        assert unit.file_type == "json"
        assert unit.placeholders == ()

    def test_translation_unit_placeholders(self):
        from app.domain.placeholders import extract_placeholders

        ph = extract_placeholders("Hello %s, you have %d items")
        unit = TranslationUnit(key="test", source_text="Hello %s", file_type="lang", placeholders=ph)
        assert len(unit.placeholders) > 0

    def test_translation_result_success(self):
        unit = TranslationUnit(key="k", source_text="src", file_type="json")
        result = TranslationResult(unit=unit, translated_text="dst", success=True)
        assert result.success
        assert result.translated_text == "dst"
        assert not result.cached
        assert result.error is None

    def test_translation_result_failure(self):
        unit = TranslationUnit(key="k", source_text="src", file_type="json")
        result = TranslationResult(unit=unit, translated_text="src", success=False, error="timeout")
        assert not result.success
        assert result.error == "timeout"

class TestTokenBucketContract:
    def test_acquire_immediate(self):
        from app.infrastructure.providers.rate_limiter import TokenBucket

        bucket = TokenBucket(rpm=600, burst=100)
        wait = bucket.acquire()
        assert wait == 0.0

    def test_acquire_depletes(self):
        from app.infrastructure.providers.rate_limiter import TokenBucket

        bucket = TokenBucket(rpm=60, burst=1)
        wait1 = bucket.acquire()
        assert wait1 == 0.0
        wait2 = bucket.acquire()
        assert wait2 > 0.0
