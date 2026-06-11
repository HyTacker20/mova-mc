from __future__ import annotations

import re
from collections import Counter

# Matches %s, %d, %f, %1$s, %2$d, %02d, %-5s, etc.
# NOTE: use _find_percent() with finditer() instead of findall() so that
# capturing groups do not strip the % prefix from results.
_PERCENT_PATTERN = re.compile(r"%(\d+\$)?[#0+\- ]?\d*\.?\d*[sdfiouxXeEgGc]")
_BRACE_PATTERN = re.compile(r"\{([^{}]*)\}")
_MINECRAFT_FORMAT_PATTERN = re.compile(r"§.", re.IGNORECASE)
# Matches {{ }} style placeholders used by some mod loaders (e.g. {{placeholder}})
_DOUBLE_BRACE_PATTERN = re.compile(r"\{\{(.+?)\}\}")


def _find_percent(text: str) -> list[str]:
    """Find all percent-style placeholders.

    Uses ``finditer`` and takes ``m.group(0)`` (the full match) so that
    capturing groups inside the pattern do not interfere.
    """
    return [m.group(0) for m in _PERCENT_PATTERN.finditer(text)]


def extract_placeholders(text: str) -> tuple[str, ...]:
    """Extract all placeholder tokens from *text*.

    Returns a deduplicated tuple preserving first-occurrence order.
    Handles: ``%s``, ``%d``, ``%1$s`` (positional), ``{name}``, ``§c`` (Minecraft
    colour codes), and ``{{placeholder}}`` (double-brace mod loader style).
    """
    result: list[str] = []
    result.extend(_find_percent(text))
    result.extend(_MINECRAFT_FORMAT_PATTERN.findall(text))
    brace_matches = _BRACE_PATTERN.findall(text)
    result.extend(f"{{{m}}}" for m in brace_matches)
    db_matches = _DOUBLE_BRACE_PATTERN.findall(text)
    result.extend(f"{{{{{m}}}}}" for m in db_matches)
    return tuple(dict.fromkeys(result))


def _count_placeholders(text: str) -> dict[str, int]:
    """Return a dict mapping each placeholder token to its occurrence count.

    Unlike *extract_placeholders* this does *not* deduplicate — it counts
    every occurrence so callers can validate that no placeholder was lost
    (or multiplied) during translation.
    """
    result: list[str] = []
    result.extend(_find_percent(text))
    result.extend(_MINECRAFT_FORMAT_PATTERN.findall(text))
    brace_matches = _BRACE_PATTERN.findall(text)
    result.extend(f"{{{m}}}" for m in brace_matches)
    db_matches = _DOUBLE_BRACE_PATTERN.findall(text)
    result.extend(f"{{{{{m}}}}}" for m in db_matches)
    return dict(Counter(result))


def validate_placeholders(original: str, translated: str) -> bool:
    """Return ``True`` if *translated* contains at least as many occurrences
    of each placeholder found in *original*.

    For positional placeholders (``%1$s``, ``%2$d``) the exact index and
    format must be preserved.  Non-positional ``%s`` may be reordered but
    the total count must match or exceed the original.

    Returns ``True`` when *original* has no placeholders.
    """
    original_counts = _count_placeholders(original)
    if not original_counts:
        return True
    translated_counts = _count_placeholders(translated)
    return all(translated_counts.get(placeholder, 0) >= count for placeholder, count in original_counts.items())
