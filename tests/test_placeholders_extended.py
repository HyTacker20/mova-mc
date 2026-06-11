"""Extended tests for placeholder extraction and validation with positional args."""

from app.domain.placeholders import (
    _count_placeholders,
    extract_placeholders,
    validate_placeholders,
)


class TestExtractPlaceholders:
    def test_basic_percent(self) -> None:
        assert extract_placeholders("Hello %s") == ("%s",)

    def test_percent_d(self) -> None:
        assert extract_placeholders("Count: %d") == ("%d",)

    def test_positional_1(self) -> None:
        result = extract_placeholders("Hello %1$s")
        assert "%1$s" in result

    def test_positional_2(self) -> None:
        result = extract_placeholders("%1$s and %2$d")
        assert "%1$s" in result
        assert "%2$d" in result

    def test_mixed_positional_and_basic(self) -> None:
        result = extract_placeholders("%1$s %s %2$d")
        assert "%1$s" in result
        assert "%s" in result
        assert "%2$d" in result

    def test_brace_placeholders(self) -> None:
        result = extract_placeholders("Hello {name}!")
        assert "{name}" in result

    def test_section_codes(self) -> None:
        result = extract_placeholders("§aGreen §rtext")
        assert "§a" in result
        assert "§r" in result

    def test_double_brace(self) -> None:
        result = extract_placeholders("{{placeholder}} test")
        assert "{{placeholder}}" in result

    def test_width_and_precision(self) -> None:
        result = extract_placeholders("%5.2f and %-10s")
        assert "%5.2f" in result
        assert "%-10s" in result

    def test_empty_text(self) -> None:
        assert extract_placeholders("") == ()
        assert extract_placeholders("No placeholders") == ()

    def test_dedup(self) -> None:
        assert extract_placeholders("%s %s %s") == ("%s",)


class TestCountPlaceholders:
    def test_single(self) -> None:
        assert _count_placeholders("Hello %s") == {"%s": 1}

    def test_multiple_same(self) -> None:
        assert _count_placeholders("%s %s %d") == {"%s": 2, "%d": 1}

    def test_positional_counts(self) -> None:
        counts = _count_placeholders("%1$s %1$s %2$d")
        assert counts["%1$s"] == 2
        assert counts["%2$d"] == 1

    def test_empty(self) -> None:
        assert _count_placeholders("") == {}


class TestValidatePlaceholders:
    def test_no_placeholders(self) -> None:
        assert validate_placeholders("Hello", "Привіт") is True

    def test_basic_valid(self) -> None:
        assert validate_placeholders("Hello %s", "Привіт %s") is True

    def test_basic_missing(self) -> None:
        assert validate_placeholders("Hello %s", "Привіт") is False

    def test_positional_valid(self) -> None:
        assert validate_placeholders("%1$s %2$d", "%1$s %2$d") is True

    def test_positional_missing(self) -> None:
        assert validate_placeholders("%1$s %2$d", "%1$s") is False

    def test_positional_wrong_index(self) -> None:
        """%1$s and %2$s are different placeholders."""
        assert validate_placeholders("%1$s %2$s", "%1$s") is False

    def test_extra_placeholders_valid(self) -> None:
        """Extra placeholders in translation are acceptable."""
        assert validate_placeholders("%s", "%s %s") is True

    def test_count_mismatch(self) -> None:
        """Original has 2 %s, translation only has 1."""
        assert validate_placeholders("%s %s", "%s") is False

    def test_reordered_non_positional(self) -> None:
        """Non-positional %s can be reordered."""
        assert validate_placeholders("%s and %s", "%s та %s") is True

    def test_mixed_types(self) -> None:
        """Mixed placeholder types all must be preserved."""
        assert validate_placeholders("%1$s: %s items §a", "%1$s: %s предметів §a") is True
        assert validate_placeholders("%1$s: %s items §a", "%s предметів §a") is False  # lost %1$s
