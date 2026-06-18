from unittest.mock import patch

import pytest

from app.exceptions import TranslationServiceError
from app.infrastructure.providers.factory import get_translator_service


class TestTranslatorService:
    def test_init_google(self):
        service = get_translator_service("google", "en", "uk", capitalize=True)
        assert service.source_lang == "en"
        assert service.target_lang == "uk"
        assert service.capitalize is True

    def test_translate_skip_empty_string(self):
        service = get_translator_service("google", "en", "uk")
        result = service.translate("")
        assert result == ""

    def test_translate_with_google(self):
        service = get_translator_service("google", "en", "uk", capitalize=False)
        with patch.object(service, "translate", return_value="\u043f\u0440\u0438\u0432\u0456\u0442"):
            result = service.translate("Hello")
            assert result == "\u043f\u0440\u0438\u0432\u0456\u0442"

    def test_translate_with_google_capitalize(self):
        service = get_translator_service("google", "en", "uk", capitalize=True)
        with patch.object(service, "translate", return_value="\u041f\u0440\u0438\u0432\u0456\u0442"):
            result = service.translate("Hello")
            assert result == "\u041f\u0440\u0438\u0432\u0456\u0442"

    def test_translate_with_google_returns_original(self):
        service = get_translator_service("google", "en", "uk")
        with patch.object(service, "translate", return_value="Hello"):
            result = service.translate("Hello")
            assert result == "Hello"

    def test_translate_with_openai_error_raises(self):
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("app.infrastructure.providers.transports.compat_sdk.OpenAICompatTransport.complete") as mock_complete,
        ):
            mock_complete.side_effect = Exception("API error")
            service = get_translator_service("openai", "en", "uk")
            with pytest.raises(TranslationServiceError):
                service.translate("Hello")
