"""Tests for OpenAILikeProvider batch translation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import TranslationResult, TranslationUnit
from app.infrastructure.providers.openai_like import OpenAILikeProvider


def _make_provider(**kwargs: object) -> OpenAILikeProvider:
    transport = MagicMock()
    transport.complete.return_value = "translated"
    transport.acomplete = AsyncMock(return_value='{"k1": "uno", "k2": "dos"}')
    defaults: dict[str, object] = {
        "source_lang": "en",
        "target_lang": "es",
        "transport": transport,
        "service_name": "test",
        "capitalize": False,
        "max_retries": 0,
        "chunk_size": 2,
        "max_concurrent_chunks": 2,
        "chunk_mode": "chunk",
    }
    defaults.update(kwargs)
    return OpenAILikeProvider(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_translate_batch_async_uses_chunks() -> None:
    provider = _make_provider(chunk_mode="chunk", chunk_size=2)
    units = [
        TranslationUnit(key=f"k{i}", source_text=f"text{i}", file_type="json")
        for i in range(4)
    ]
    results = await provider.translate_batch_async(units)
    assert len(results) == 4
    assert all(r.success for r in results)
    assert provider._transport.acomplete.await_count == 2


@pytest.mark.asyncio
async def test_translate_batch_async_on_entry_called() -> None:
    provider = _make_provider(chunk_mode="item")
    units = [TranslationUnit(key="k1", source_text="hi", file_type="json")]
    provider._transport.acomplete = AsyncMock(return_value="hola")
    seen: list[tuple[str, str, str]] = []

    await provider.translate_batch_async(units, on_entry=lambda k, s, t: seen.append((k, s, t)))

    assert seen == [("k1", "hi", "hola")]


@pytest.mark.asyncio
async def test_hinted_units_translated_individually() -> None:
    provider = _make_provider(chunk_mode="chunk", chunk_size=10)
    provider._transport.acomplete = AsyncMock(return_value="hinted")
    units = [
        TranslationUnit(key="plain", source_text="a", file_type="json"),
        TranslationUnit(key="hinted", source_text="b", file_type="json", hint_text="подсказка"),
    ]
    await provider.translate_batch_async(units)
    payloads = [call.args[0][1]["content"] for call in provider._transport.acomplete.await_args_list]
    assert all(not content.startswith("{") for content in payloads)


@pytest.mark.asyncio
async def test_auto_mode_token_budget_chunks() -> None:
    provider = _make_provider(chunk_mode="auto", chunk_token_budget=80, chunk_size=25)
    long_text = "word " * 30
    provider._transport.acomplete = AsyncMock(
        side_effect=lambda messages, **kw: json.dumps(
            {k: f"tr_{k}" for k in json.loads(messages[1]["content"])}
        )
    )
    units = [
        TranslationUnit(key=f"k{i}", source_text=long_text, file_type="json")
        for i in range(6)
    ]
    results = await provider.translate_batch_async(units)
    assert len(results) == 6
    assert provider._transport.acomplete.await_count >= 2


def test_translate_batch_sync_uses_chunks() -> None:
    provider = _make_provider(chunk_mode="chunk", chunk_size=2)
    provider._transport.complete.return_value = '{"k1": "uno", "k2": "dos"}'
    units = [
        TranslationUnit(key="k1", source_text="a", file_type="json"),
        TranslationUnit(key="k2", source_text="b", file_type="json"),
    ]
    results = provider.translate_batch(units)
    assert len(results) == 2
    assert all(isinstance(r, TranslationResult) and r.success for r in results)
