"""Shared utility functions for translation providers."""

from __future__ import annotations


def capitalize_first(text: str) -> str:
    """Capitalise only the first character, leave the rest untouched.

    Unlike ``str.capitalize()`` which lowercases all other characters,
    this preserves the original casing of the rest of the string.

    Examples::

        capitalize_first("hello WORLD") → "Hello WORLD"
        capitalize_first("") → ""
    """
    return text[0].upper() + text[1:] if text else text
