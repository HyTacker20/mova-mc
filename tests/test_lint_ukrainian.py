"""Tests for the Ukrainian-language QA lint function."""

from app.domain.lint import lint_ukrainian


class TestLintUkrainian:
    def test_clean_ukrainian(self) -> None:
        """Pure Ukrainian text without issues should return no warnings."""
        result = lint_ukrainian("Привіт, це чиста українська мова без проблем.")
        assert result == []

    def test_russian_letter_yo(self) -> None:
        """Detect Russian letter ё."""
        result = lint_ukrainian("Це речення з помилкою: ёлка.")
        assert len(result) >= 1
        assert result[0]["type"] == "russian_letter"

    def test_russian_letter_y(self) -> None:
        """Detect Russian letter ы."""
        result = lint_ukrainian("Це речення з помилкою: мы.")
        russian_issues = [w for w in result if w["type"] == "russian_letter"]
        assert len(russian_issues) >= 1

    def test_russian_letter_soft_sign(self) -> None:
        """Detect Russian letter ь used as ъ."""
        result = lint_ukrainian("З'їв - це правильно, а зъїв - ні.")
        russian_issues = [w for w in result if w["type"] == "russian_letter"]
        assert len(russian_issues) >= 1

    def test_capitalized_noun_not_flagged(self) -> None:
        """Capitalized proper nouns (mod names, etc.) should NOT be flagged."""
        result = lint_ukrainian("Це текст з Pickle словом всередині.")
        latin_issues = [w for w in result if w["type"] == "latin_remnant"]
        assert latin_issues == []

    def test_camelcase_not_flagged(self) -> None:
        """CamelCase/PascalCase names should NOT be flagged."""
        result = lint_ukrainian("Тут згадується MonkaS та PickleTweaks.")
        latin_issues = [w for w in result if w["type"] == "latin_remnant"]
        assert latin_issues == []

    def test_lower_upper_mix_not_flagged(self) -> None:
        """Lower+upper mix like formatting remnants should NOT be flagged."""
        result = lint_ukrainian("Натисніть oSHIFT для інфи.")
        latin_issues = [w for w in result if w["type"] == "latin_remnant"]
        assert latin_issues == []

    def test_placeholder_ignored(self) -> None:
        """Placeholders like %s, %d should NOT trigger latin detection."""
        result = lint_ukrainian("Привіт %s, у тебе предметів.")
        latin_issues = [w for w in result if w["type"] == "latin_remnant"]
        assert latin_issues == []

    def test_empty_text(self) -> None:
        """Empty text should produce no warnings."""
        result = lint_ukrainian("")
        assert result == []

    def test_acronym_not_flagged(self) -> None:
        """Short all-caps acronyms should not be flagged as Latin remnants."""
        result = lint_ukrainian("Гра підтримує API модів.")
        latin_issues = [w for w in result if w["type"] == "latin_remnant"]
        assert latin_issues == []
