"""Domain-level lint / QA helpers for translation quality checks.

All functions in this module are pure — they operate on strings and return
structured results without I/O or side effects.
"""

from __future__ import annotations

import re

# Russian-specific Cyrillic letters that do NOT exist in the Ukrainian alphabet
_RUSSIAN_ONLY_LETTERS = re.compile(r"[ёъыэЁЪЫЭ]")

# Guess at a "word" made of ASCII letters — candidates for untranslated remnants
_LATIN_WORD = re.compile(r"\b[A-Za-z]{4,}\b")

# Tokens that should be ignored by the Latin-word check
_LATIN_EXCEPTIONS: re.Pattern[str] = re.compile(
    r"^\d+$"  # pure numbers
    r"|^§[0-9a-fk-or]$"  # Minecraft §-codes
    r"|^%(?:\d+\$)?[#0+\- ]?\d*\.?\d*[sdfiouxXeEgGc]$"  # %-placeholders
    r"|^\{.*\}$"  # {braces}
    r"|^\{\{.*\}\}$"  # {{double braces}}
    r"|^[A-Z]+$"  # acronyms (all-caps)
    r"|^[a-z]+$"  # single lower-case word (likely a key)
    r"|^[A-Z][a-z]+$"  # capitalized word (proper noun — mod/item name)
    r"|^(?:[A-Z][a-z]+)+[A-Z]?[a-z]*$"  # PascalCase / CamelCase ("MonkaS")
    r"|^[a-z]+[A-Z][a-zA-Z]*$"  # lower prefix + upper suffix ("oSHIFT")
)


def lint_ukrainian(text: str) -> list[dict]:
    """Check *text* for common quality issues in Ukrainian translation.

    Returns a list of warning dicts, each with keys:

    * ``type`` — short identifier (``"russian_letter"``, ``"latin_remnant"``)
    * ``message`` — human-readable description
    * ``position`` — character index in *text*, or ``None``

    Returns an empty list when no issues are found.

    .. note::

        This is a *soft* lint — returned warnings should never cause a
        translation to be rejected. They are purely informational.
    """
    warnings: list[dict] = []

    # —— Russian-only letters ——
    for m in _RUSSIAN_ONLY_LETTERS.finditer(text):
        warnings.append(
            {
                "type": "russian_letter",
                "message": f"Russian letter '{m.group()}' found — possible russism/calque",
                "position": m.start(),
            }
        )

    # —— Untranslated Latin remnants ——
    for m in _LATIN_WORD.finditer(text):
        word = m.group()
        if _LATIN_EXCEPTIONS.match(word):
            continue
        warnings.append(
            {
                "type": "latin_remnant",
                "message": f"Possible untranslated text: '{word}'",
                "position": m.start(),
            }
        )

    return warnings
