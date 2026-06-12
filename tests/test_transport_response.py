"""Tests for the shared chat-completion content extractor."""

from types import SimpleNamespace

from app.infrastructure.providers.transports._response import extract_content


def _completion(
    content: str | None,
    *,
    finish_reason: str = "stop",
    reasoning_content: str | None = None,
    reasoning_tokens: int | None = None,
):
    """Build a minimal object shaped like an OpenAI chat completion."""
    message = SimpleNamespace(content=content, reasoning_content=reasoning_content)
    details = SimpleNamespace(reasoning_tokens=reasoning_tokens)
    usage = SimpleNamespace(completion_tokens_details=details)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage)


class TestExtractContent:
    def test_returns_plain_content(self):
        assert extract_content(_completion("Привіт"), transport="T") == "Привіт"

    def test_strips_surrounding_whitespace(self):
        assert extract_content(_completion("  Привіт  "), transport="T") == "Привіт"

    def test_strips_think_block(self):
        comp = _completion("<think>reasoning here</think>\nПривіт")
        assert extract_content(comp, transport="T") == "Привіт"

    def test_strips_think_block_case_insensitive_multiline(self):
        comp = _completion("<THINK>\nmulti\nline\n</THINK>Відповідь")
        assert extract_content(comp, transport="T") == "Відповідь"

    def test_strips_lowercase_think_tags(self):
        comp = _completion("\x3cthink\x3ereasoning\x3c/think\x3eПривіт")
        assert extract_content(comp, transport="T") == "Привіт"

    def test_think_only_content_becomes_empty(self):
        assert extract_content(_completion("<think>only thinking</think>"), transport="T") == ""

    def test_empty_content_length_finish_returns_empty(self):
        comp = _completion("", finish_reason="length", reasoning_tokens=1000)
        assert extract_content(comp, transport="T") == ""

    def test_empty_content_with_reasoning_content_returns_empty(self):
        comp = _completion("", reasoning_content="thinking...")
        assert extract_content(comp, transport="T") == ""

    def test_none_content_returns_empty(self):
        assert extract_content(_completion(None), transport="T") == ""

    def test_malformed_completion_no_choices_returns_empty(self):
        assert extract_content(SimpleNamespace(choices=[]), transport="T") == ""
