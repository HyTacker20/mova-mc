"""Tests for Google provider — async methods, batch, edge cases."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.domain.models import TranslationResult, TranslationUnit
from app.infrastructure.providers.google import GoogleProvider


class TestGoogleAsync:
    """Tests for async methods of GoogleProvider."""

    @pytest.mark.asyncio
    async def test_translate_async_success(self) -> None:
        provider = GoogleProvider("en", "uk", max_retries=0)
        with patch.object(provider, "translate", return_value="Привіт") as mock_trans:
            result = await provider.translate_async("Hello")
        assert result == "Привіт"
        mock_trans.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_translate_unit_async_success(self) -> None:
        provider = GoogleProvider("en", "uk", max_retries=0)
        unit = TranslationUnit(key="k1", source_text="Hello", file_type="json")
        expected = TranslationResult(unit=unit, translated_text="Привіт", success=True)
        with patch.object(provider, "translate_unit", return_value=expected):
            result = await provider.translate_unit_async(unit)
        assert result.success is True
        assert result.translated_text == "Привіт"

    @pytest.mark.asyncio
    async def test_translate_batch_async_empty(self) -> None:
        provider = GoogleProvider("en", "uk")
        results = await provider.translate_batch_async([])
        assert results == []

    @pytest.mark.asyncio
    async def test_translate_batch_async_success(self) -> None:
        provider = GoogleProvider("en", "uk", max_retries=0)
        units = [
            TranslationUnit(key="k1", source_text="Hello", file_type="json"),
            TranslationUnit(key="k2", source_text="World", file_type="json"),
        ]

        async def _fake_translate_unit(unit: TranslationUnit) -> TranslationResult:
            return TranslationResult(
                unit=unit,
                translated_text=f"tr_{unit.source_text}",
                success=True,
            )

        with patch.object(provider, "translate_unit_async", side_effect=_fake_translate_unit):
            results = await provider.translate_batch_async(units)

        assert len(results) == 2
        assert results[0].translated_text == "tr_Hello"
        assert results[1].translated_text == "tr_World"
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_translate_batch_async_with_callback(self) -> None:
        provider = GoogleProvider("en", "uk", max_retries=0)
        units = [
            TranslationUnit(key="k1", source_text="A", file_type="json"),
            TranslationUnit(key="k2", source_text="B", file_type="json"),
        ]
        calls: list[tuple] = []

        def on_entry(key: str, src: str, tgt: str) -> None:
            calls.append((key, src, tgt))

        async def _fake_translate_unit(unit: TranslationUnit) -> TranslationResult:
            return TranslationResult(
                unit=unit,
                translated_text=f"tr_{unit.source_text}",
                success=True,
            )

        with patch.object(provider, "translate_unit_async", side_effect=_fake_translate_unit):
            await provider.translate_batch_async(units, on_entry=on_entry)

        assert len(calls) == 2
        assert calls[0] == ("k1", "A", "tr_A")
        assert calls[1] == ("k2", "B", "tr_B")

    @pytest.mark.asyncio
    async def test_translate_batch_async_partial_failure(self) -> None:
        provider = GoogleProvider("en", "uk", max_retries=0)
        units = [
            TranslationUnit(key="k1", source_text="A", file_type="json"),
            TranslationUnit(key="k2", source_text="B", file_type="json"),
        ]

        async def _fake_translate_unit(unit: TranslationUnit) -> TranslationResult:
            if unit.source_text == "B":
                raise RuntimeError("fail")
            return TranslationResult(
                unit=unit,
                translated_text=f"tr_{unit.source_text}",
                success=True,
            )

        with patch.object(provider, "translate_unit_async", side_effect=_fake_translate_unit):
            results = await provider.translate_batch_async(units)

        assert results[0].success is True
        assert results[0].translated_text == "tr_A"
        assert results[1].success is False
        assert results[1].translated_text == "B"  # original text on failure

    @pytest.mark.asyncio
    async def test_translate_batch_async_parallel(self) -> None:
        """Verify that concurrent workers are limited by semaphore."""
        provider = GoogleProvider("en", "uk", max_retries=0, max_concurrent_chunks=2)
        units = [TranslationUnit(key=f"k{i}", source_text=f"text{i}", file_type="json") for i in range(5)]

        concurrent_count = 0
        max_concurrent = 0

        async def _fake_translate_unit(unit: TranslationUnit) -> TranslationResult:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)
            concurrent_count -= 1
            return TranslationResult(unit=unit, translated_text=f"tr_{unit.source_text}", success=True)

        with patch.object(provider, "translate_unit_async", side_effect=_fake_translate_unit):
            results = await provider.translate_batch_async(units)

        assert len(results) == 5
        # With max_concurrent_chunks=2, we should not exceed 2 concurrent
        assert max_concurrent <= 2


class TestGoogleBatchSync:
    """Tests for sync translate_batch method."""

    def test_translate_batch_success(self) -> None:
        provider = GoogleProvider("en", "uk", max_retries=0)
        units = [
            TranslationUnit(key="k1", source_text="A", file_type="json"),
            TranslationUnit(key="k2", source_text="B", file_type="json"),
        ]

        with patch.object(provider, "translate", side_effect=["tr_A", "tr_B"]):
            results = provider.translate_batch(units)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].translated_text == "tr_A"
        assert results[1].translated_text == "tr_B"

    def test_translate_batch_partial_failure(self) -> None:
        provider = GoogleProvider("en", "uk", max_retries=0)
        units = [
            TranslationUnit(key="k1", source_text="A", file_type="json"),
            TranslationUnit(key="k2", source_text="B", file_type="json"),
        ]

        def _fake_translate(text: str) -> str:
            if text == "B":
                raise RuntimeError("fail")
            return f"tr_{text}"

        with patch.object(provider, "translate", side_effect=_fake_translate):
            results = provider.translate_batch(units)

        assert results[0].success is True
        assert results[1].success is False
        assert results[1].translated_text == "B"
        assert results[1].error == "fail"
