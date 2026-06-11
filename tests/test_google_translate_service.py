from unittest.mock import patch

from app.domain.models import TranslationUnit
from app.infrastructure.providers.google import GoogleProvider

def _mock_translate_fn(text: str) -> str:
    if text == "fail":
        raise RuntimeError("translation failed")
    return f"tr_{text}"

class TestGoogleProvider:
    def test_translate_empty_string(self):
        provider = GoogleProvider("en", "uk")
        assert provider.translate("") == ""

    def test_translate_capitalize(self):
        provider = GoogleProvider("en", "uk", capitalize=True, max_retries=0)
        with patch.object(provider, "_translator") as mock_translator:
            mock_translator.translate.return_value = "привіт"
            result = provider.translate("hello")
            assert result == "Привіт"

    def test_translate_unit_failure(self):
        provider = GoogleProvider("en", "uk", capitalize=False, max_retries=0)
        unit = TranslationUnit(key="k1", source_text="hello", file_type="json")
        with patch.object(provider, "_translate_text", side_effect=RuntimeError("translation failed")):
            result = provider.translate_unit(unit)
        assert result.unit == unit
        assert result.translated_text == "hello"
        assert result.success is False
        assert result.error == "translation failed"

def _patch_translate(provider, fn):
    return patch.object(provider, "translate", side_effect=fn)
