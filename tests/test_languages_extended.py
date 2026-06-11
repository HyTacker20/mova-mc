"""Tests for extended language registry functions."""

from app.domain.languages import get_language_english_name, get_language_name, is_valid_language


class TestGetLanguageEnglishName:
    def test_ukrainian(self) -> None:
        assert get_language_english_name("uk_UA") == "Ukrainian"

    def test_english_us(self) -> None:
        assert get_language_english_name("en_US") == "English United States"

    def test_russian(self) -> None:
        assert get_language_english_name("ru_RU") == "Russian"

    def test_portuguese_brazil(self) -> None:
        assert get_language_english_name("pt_BR") == "Portuguese Brazil"

    def test_spanish_mexico(self) -> None:
        assert get_language_english_name("es_MX") == "Spanish Mexico"

    def test_chinese_simplified(self) -> None:
        assert get_language_english_name("zh_CN") == "Chinese Simplified"

    def test_fallback_for_unknown_code(self) -> None:
        assert get_language_english_name("xx_XX") == "xx_XX"

    def test_get_language_name_still_works(self) -> None:
        name = get_language_name("uk_UA")
        assert "Ukrainian" in name
        assert "uk_UA" in name

    def test_is_valid_language_still_works(self) -> None:
        assert is_valid_language("uk_UA") is True
        assert is_valid_language("xx_XX") is False
