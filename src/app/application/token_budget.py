"""Token-budget helpers for grouping translation units into API chunks."""

from __future__ import annotations

# Rough JSON overhead per key-value pair (quotes, colon, comma, key name).
_JSON_PAIR_OVERHEAD = 12


def estimate_tokens(text: str) -> int:
    """Estimate token count for mixed EN/UK Minecraft localization text."""
    return max(1, len(text) // 4)


def _chunk_token_cost(key: str, text: str) -> int:
    return estimate_tokens(text) + estimate_tokens(key) + _JSON_PAIR_OVERHEAD


def build_token_chunks(
    items: list[tuple[str, str]],
    *,
    max_input_tokens: int,
    max_items: int,
    max_text_length: int,
) -> tuple[list[list[tuple[str, str]]], list[tuple[str, str]]]:
    """Split *items* into batchable chunks and long single-item entries.

    Returns ``(chunks, long_items)`` where each chunk respects *max_input_tokens*
    and *max_items*, and entries longer than *max_text_length* are returned
    separately for individual translation.
    """
    if not items:
        return [], []

    short_items: list[tuple[str, str]] = []
    long_items: list[tuple[str, str]] = []
    for key, text in items:
        if len(text) > max_text_length:
            long_items.append((key, text))
        else:
            short_items.append((key, text))

    if not short_items:
        return [], long_items

    if max_items <= 0:
        return [short_items], long_items

    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0

    for key, text in short_items:
        item_cost = _chunk_token_cost(key, text)
        would_exceed_budget = current and current_tokens + item_cost > max_input_tokens
        would_exceed_count = len(current) >= max_items

        if would_exceed_budget or would_exceed_count:
            chunks.append(current)
            current = []
            current_tokens = 0

        current.append((key, text))
        current_tokens += item_cost

    if current:
        chunks.append(current)

    return chunks, long_items
