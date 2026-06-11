"""Glossary loader for injecting Minecraft terminology into translation prompts.

The glossary helps LLM providers use consistent, official Minecraft terminology
instead of guessing translations for blocks, items, mobs, etc.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_glossary(lang_code: str) -> dict[str, str]:
    """Load the glossary for *lang_code* (e.g. ``"uk_UA"``).

    Returns an empty dict when no glossary file exists for that language.
    """
    path = _glossary_path(lang_code)
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        return {}


def _glossary_path(lang_code: str) -> Path:
    """Return the expected filesystem path for a glossary file."""
    return Path(__file__).resolve().parent.parent.parent / "data" / "glossary" / f"{lang_code}.json"


def get_relevant_terms(glossary: dict[str, str], source_texts: list[str]) -> str:
    """Build a ``"Use this terminology:"`` snippet from glossary entries whose
    English key appears in the given *source_texts*.

    Returns an empty string when no terms are relevant or the glossary is empty.
    """
    if not glossary or not source_texts:
        return ""

    # Collect unique English terms that appear in at least one source text
    relevant: list[tuple[str, str]] = []
    seen: set[str] = set()

    for en_term, uk_term in glossary.items():
        if en_term in seen:
            continue
        lower_en = en_term.lower()
        if any(lower_en in src.lower() for src in source_texts):
            relevant.append((en_term, uk_term))
            seen.add(en_term)

    if not relevant:
        return ""

    terms_str = ", ".join(f"{en}→{uk}" for en, uk in relevant)
    return f"Use this terminology: {terms_str}."


# --- User glossary support ---


def load_user_glossary(path: str | None) -> dict[str, str]:
    """Load a custom user-provided glossary from *path*.

    Returns an empty dict when *path* is falsy or the file cannot be read.
    """
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        with file_path.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        return {}


def load_merged_glossary(lang_code: str, user_path: str | None = None) -> dict[str, str]:
    """Load the built-in glossary for *lang_code* merged with an optional
    user glossary at *user_path*.

    User entries take precedence over built-in ones for the same English key.
    Returns an empty dict when neither source provides terms.
    """
    merged = load_glossary(lang_code)
    merged.update(load_user_glossary(user_path))
    return merged
