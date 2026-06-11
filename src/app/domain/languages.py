from __future__ import annotations

import re

from ..data import load_languages as _load_languages

_LANG_DATA = _load_languages()
LANGUAGE_OPTIONS: list[dict[str, str]] = _LANG_DATA
LANGUAGE_NAMES: dict[str, str] = {opt["value"]: opt["name"] for opt in _LANG_DATA}

# Cache for english_name lookups
_ENGLISH_NAME_CACHE: dict[str, str] = {}

# Pattern to strip trailing " (code)" suffix: e.g. "English United States (en_US)" → "English United States"
_TRAILING_CODE_RE = re.compile(r"\s+\([^)]+\)\s*$")


def get_language_english_name(code: str) -> str:
    """Return a human-readable English name for the given language code.

    Strips the trailing `` (code)`` suffix from the stored display name.
    Examples::

        get_language_english_name("uk_UA")  → "Ukrainian"
        get_language_english_name("en_US")  → "English United States"
        get_language_english_name("pt_BR")  → "Portuguese Brazil"
        get_language_english_name("xx_XX")  → "xx_XX"  (fallback)
    """
    if code in _ENGLISH_NAME_CACHE:
        return _ENGLISH_NAME_CACHE[code]

    display = LANGUAGE_NAMES.get(code)
    if display is None:
        _ENGLISH_NAME_CACHE[code] = code
        return code

    english = _TRAILING_CODE_RE.sub("", display).strip()
    _ENGLISH_NAME_CACHE[code] = english
    return english


def get_language_options() -> list[dict[str, str]]:
    return LANGUAGE_OPTIONS


def get_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def is_valid_language(code: str) -> bool:
    return code in LANGUAGE_NAMES
