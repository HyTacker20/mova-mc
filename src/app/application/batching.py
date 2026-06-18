from __future__ import annotations

import json
import re
from typing import Any

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*$", re.MULTILINE)

# Trailing comma before closing brace (common LLM mistake)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def chunk_list(items: list[Any], chunk_size: int) -> list[list[Any]]:
    if chunk_size <= 0:
        return [items]
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def parse_chunk_response(response: str) -> dict[str, str] | None:
    text = response.strip()

    # Remove markdown code fences (```json ... ```)
    text = _CODE_FENCE_RE.sub("", text).strip()

    # Extract JSON object — find first { and last }, discard surrounding text
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    # Handle trailing commas before closing braces (common LLM mistake)
    text = _TRAILING_COMMA_RE.sub(r"\1", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if isinstance(v, str)}
    except json.JSONDecodeError:
        pass

    return None


def filter_empty(data: dict[str, str]) -> tuple[list[tuple[str, str]], dict[str, str]]:
    non_empty = [(k, v) for k, v in data.items() if v and isinstance(v, str)]
    empty_items: dict[str, str] = {}
    for k, v in data.items():
        if not v or not isinstance(v, str):
            empty_items[k] = str(v) if not isinstance(v, str) and v is not None else v or ""
    return non_empty, empty_items
