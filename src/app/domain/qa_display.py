"""Rich-markup formatting for QA fields on a TranslationResult."""

from __future__ import annotations

import re

_GENERIC_KEY_SUFFIXES = frozenset({"name", "text", "desc", "title", "tooltip", "label"})
_MC_TAG_RE = re.compile(
    r"</?(?:item|imp|r|bold|italic|underlined|strikethrough|c|link)[^>]*>",
    re.IGNORECASE,
)
_SECTION_CODE_RE = re.compile(r"§.")


def format_qa_key(key: str) -> str:
    """Return a short but distinctive label for a lang-file key."""
    parts = key.split(".")
    if len(parts) <= 1:
        return key
    last = parts[-1]
    if last.isdigit() or last.lower() in _GENERIC_KEY_SUFFIXES:
        if len(parts) >= 2:
            return f"{parts[-2]}.{last}"
    return last


def strip_mc_formatting(text: str) -> str:
    """Remove Minecraft rich-text tags and colour codes for display."""
    cleaned = _MC_TAG_RE.sub("", text)
    return _SECTION_CODE_RE.sub("", cleaned).strip()


def truncate_preview(text: str, max_len: int = 80) -> str:
    """Truncate *text* for log/UI previews."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def format_text_change_preview(original: str, fixed: str, max_len: int = 80) -> str:
    """Format orig→fixed with MC tags stripped and length capped."""
    orig = truncate_preview(strip_mc_formatting(original), max_len)
    fixed = truncate_preview(strip_mc_formatting(fixed), max_len)
    return f'"{orig}" → "{fixed}"'


def format_provider_model(provider: str, model: str) -> str:
    """Format provider/model for display without duplicating the provider prefix."""
    if not model:
        return provider
    if not provider:
        return model
    prefix = f"{provider}/"
    if model.startswith(prefix):
        return model
    return f"{provider}/{model}"
