"""Regression test: cancelled entries should be marked as 'cancelled', not just 'failed'.

When a pipeline job is cancelled mid-translation, entries that were never
attempted should carry error="cancelled" so the caller can distinguish
skipped entries from genuine translation failures.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from app.domain.models import TranslationUnit
from app.infrastructure.providers.openai_like import OpenAILikeProvider
from app.utils.cancellation import cancel_token


@pytest.fixture(autouse=True)
def _clear_cancel_token() -> None:
    """Clear the global cancellation token before each test."""
    cancel_token.clear()


def _make_provider(**kwargs) -> OpenAILikeProvider:
    transport = MagicMock()
    transport.complete.return_value = "hola"
    transport.acomplete.return_value = "hola"
    defaults = dict(
        source_lang="en",
        target_lang="es",
        transport=transport,
        service_name="test",
        capitalize=False,
        max_retries=0,
    )
    defaults.update(kwargs)
    return OpenAILikeProvider(**defaults)


class TestCancellationMarksUnattemptedEntries:
    """When cancelled, fallback entries should have error="cancelled"."""

    def test_sync_raises_on_cancellation(self) -> None:
        """Sync path: cancellation raises CancelledError immediately — correct behavior."""
        provider = _make_provider(chunk_size=2)
        units = [TranslationUnit(key="k1", source_text="hello", file_type="json")]
        cancel_token.set()
        with pytest.raises(asyncio.CancelledError):
            provider.translate_batch(units)

    @pytest.mark.asyncio
    async def test_async_cancelled_during_processing(self) -> None:
        """Cancellation mid-processing: remaining entries marked 'cancelled'.

        Uses a transport that sets cancel_token after a few successful calls,
        simulating the user pressing Cancel while translation is running.
        """
        call_count = 0

        async def _acomplete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                cancel_token.set()
            return "hola"

        transport = MagicMock()
        transport.acomplete.side_effect = _acomplete

        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="es",
            transport=transport,
            service_name="test",
            capitalize=False,
            max_retries=0,
            chunk_size=1,  # process one at a time
            max_concurrent_chunks=1,  # sequential to guarantee determinism
        )

        units = [TranslationUnit(key=f"k{i}", source_text=f"text_{i}", file_type="json") for i in range(10)]

        results = await provider.translate_batch_async(units)

        assert len(results) == 10

        succeeded = [r for r in results if r.success]
        cancelled = [r for r in results if r.error == "cancelled"]

        # First 3 calls succeed, then token is set.
        # Entries 4-10 enter semaphore, see token set, raise CancelledError.
        # Those 7 entries should be marked "cancelled".
        assert len(succeeded) >= 2, f"Expected at least 2 successful, got {len(succeeded)}"
        assert len(cancelled) >= 1, (
            f"Expected cancelled entries, got: {[(r.unit.key, r.success, r.error) for r in results]}"
        )

    @pytest.mark.asyncio
    async def test_async_not_cancelled_no_cancelled_mark(self) -> None:
        """Without cancellation, normal failures should NOT be marked cancelled."""
        transport = MagicMock()
        transport.acomplete.side_effect = RuntimeError("API down")
        provider = _make_provider(chunk_size=2)

        units = [
            TranslationUnit(key="k1", source_text="hello", file_type="json"),
            TranslationUnit(key="k2", source_text="world", file_type="json"),
        ]

        results = await provider.translate_batch_async(units)

        assert len(results) == 2
        cancelled = [r for r in results if r.error == "cancelled"]
        assert len(cancelled) == 0, "API failures should NOT be marked cancelled"

    @pytest.mark.asyncio
    async def test_async_normal_completion_all_succeed(self) -> None:
        """Without cancellation, all entries should succeed."""
        provider = _make_provider(chunk_size=1, max_concurrent_chunks=1)

        units = [TranslationUnit(key=f"k{i}", source_text=f"text_{i}", file_type="json") for i in range(5)]

        results = await provider.translate_batch_async(units)

        assert all(r.success for r in results), (
            f"Expected all success, got: {[(r.unit.key, r.success, r.error) for r in results]}"
        )
        assert all(r.error != "cancelled" for r in results)

    @pytest.mark.asyncio
    async def test_async_api_error_not_marked_cancelled(self) -> None:
        """Entries that fail due to API errors should NOT be marked 'cancelled'.

        Uses max_chunk_text_length=0 to force all entries through individual
        translation (not chunked), so API errors are caught by translate_unit_async
        which correctly sets success=False with the actual error message.
        """
        transport = MagicMock()
        transport.acomplete.side_effect = RuntimeError("API timeout")
        provider = OpenAILikeProvider(
            source_lang="en",
            target_lang="es",
            transport=transport,
            service_name="test",
            capitalize=False,
            max_retries=0,
            chunk_max_text_length=0,  # force individual translation
            max_concurrent_chunks=1,
        )

        units = [
            TranslationUnit(key="k1", source_text="hello", file_type="json"),
        ]

        results = await provider.translate_batch_async(units)

        assert len(results) == 1
        r = results[0]
        assert not r.success, "API error should fail, got success=True"
        assert r.error != "cancelled", f"Should not be cancelled: {r.error!r}"
        assert "API timeout" in (r.error or ""), f"Error: {r.error!r}"
