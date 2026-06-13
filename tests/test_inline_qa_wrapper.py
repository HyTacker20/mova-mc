"""Tests for InlineQaWrapper streaming QA."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from app.domain.models import TranslationResult, TranslationUnit
from app.infrastructure.providers.judge import LlmJudge, Verdict
from app.infrastructure.providers import qa_wrapper as qa_wrapper_module
from app.infrastructure.providers.qa_wrapper import InlineQaWrapper
from app.utils.cancellation import cancel_token


@pytest.fixture(autouse=True)
def _clear_cancel_token() -> None:
    cancel_token.clear()
    qa_wrapper_module._INLINE_QA_STATUS_EMITTED = False
    yield
    cancel_token.clear()
    qa_wrapper_module._INLINE_QA_STATUS_EMITTED = False


class _RecordingProgress:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def report(self, event: str, **data: object) -> None:
        self.events.append((event, dict(data)))

    def report_qa_progress(self, done: int, total: int) -> None:
        self.events.append(("qa_progress", {"done": done, "total": total}))


class _MockInner:
    def __init__(self, units: list[TranslationUnit], *, delay: float = 0.0) -> None:
        self._units = units
        self._delay = delay
        self.call_log: list[str] = []

    async def translate_batch_async(
        self,
        units: list[TranslationUnit],
        *,
        on_entry: object | None = None,
    ) -> list[TranslationResult]:
        results: list[TranslationResult] = []
        for unit in units:
            if self._delay:
                await asyncio.sleep(self._delay)
            translated = f"bad-{unit.source_text}"
            if callable(on_entry):
                on_entry(unit.key, unit.source_text, translated)
            self.call_log.append(f"translated-{unit.key}")
            results.append(TranslationResult(unit=unit, translated_text=translated, success=True))
        return results


def _make_judge(
    verdicts: dict[str, Verdict] | None = None,
    *,
    call_log: list[str] | None = None,
) -> MagicMock:
    judge = MagicMock(spec=LlmJudge)
    judge._chunk_size = 5

    def _judge_batch(items: list[tuple[str, str, str]]) -> dict[str, Verdict]:
        if call_log is not None:
            call_log.append("judge")
        out: dict[str, Verdict] = {}
        for key, _src, _tgt in items:
            out[key] = (verdicts or {}).get(key, Verdict("ok"))
        return out

    judge.judge_batch.side_effect = _judge_batch
    return judge


class TestInlineQaWrapper:
    def test_applies_safe_judge_fix_to_results(self) -> None:
        units = [TranslationUnit(key="k1", source_text="Stone axe", file_type="lang")]
        inner = _MockInner(units)
        judge = _make_judge(
            {
                "k1": Verdict(
                    verdict="flag",
                    score=1,
                    issue="grammar",
                    fix="Кам'яна сокира",
                ),
            }
        )
        progress = _RecordingProgress()
        wrapper = InlineQaWrapper(
            inner,
            judge,
            threshold=3,
            chunk_size=5,
            progress=progress,
        )

        results = asyncio.run(wrapper.translate_batch_async(units))

        assert results[0].translated_text == "Кам'яна сокира"
        meta = wrapper.consume_qa_metadata()
        assert meta["k1"][0] == 1
        event_names = [e for e, _ in progress.events]
        assert "qa_inline_judging" in event_names
        assert "qa_verdict" in event_names
        assert "qa_inline_fix" in event_names
        qa_progress = [data for event, data in progress.events if event == "qa_progress"]
        assert qa_progress
        assert qa_progress[-1] == {"done": 1, "total": 1}

    def test_emits_qa_progress_after_batch(self) -> None:
        units = [
            TranslationUnit(key="k1", source_text="A", file_type="lang"),
            TranslationUnit(key="k2", source_text="B", file_type="lang"),
        ]
        inner = _MockInner(units)
        judge = _make_judge()
        progress = _RecordingProgress()
        wrapper = InlineQaWrapper(inner, judge, chunk_size=5, progress=progress)

        asyncio.run(wrapper.translate_batch_async(units))

        qa_progress = [data for event, data in progress.events if event == "qa_progress"]
        assert qa_progress[-1] == {"done": 2, "total": 2}

    def test_drains_partial_batch_without_full_chunk(self) -> None:
        units = [
            TranslationUnit(key="k1", source_text="A", file_type="lang"),
            TranslationUnit(key="k2", source_text="B", file_type="lang"),
        ]
        inner = _MockInner(units)
        judge = _make_judge()
        wrapper = InlineQaWrapper(inner, judge, chunk_size=5)

        asyncio.run(wrapper.translate_batch_async(units))

        judge.judge_batch.assert_called_once()
        batch = judge.judge_batch.call_args[0][0]
        assert len(batch) == 2

    def test_judges_during_translation_when_chunk_fills(self) -> None:
        units = [TranslationUnit(key=f"k{i}", source_text=f"text{i}", file_type="lang") for i in range(6)]
        inner = _MockInner(units, delay=0.05)
        call_log: list[str] = []
        judge = _make_judge(call_log=call_log)
        wrapper = InlineQaWrapper(inner, judge, chunk_size=3)

        asyncio.run(wrapper.translate_batch_async(units))

        assert call_log.count("judge") >= 1
        first_judge_idx = call_log.index("judge")
        last_translate_idx = max(i for i, entry in enumerate(inner.call_log) if entry.startswith("translated-"))
        assert first_judge_idx < last_translate_idx

    def test_skips_rejudge_for_structurally_safe_fix(self) -> None:
        units = [TranslationUnit(key="k1", source_text="Hello world", file_type="lang")]
        inner = _MockInner(units)
        judge = _make_judge(
            {
                "k1": Verdict(
                    verdict="flag",
                    score=2,
                    issue="grammar",
                    fix="Hello brave world",
                ),
            }
        )
        wrapper = InlineQaWrapper(inner, judge, threshold=3, chunk_size=5)

        results = asyncio.run(wrapper.translate_batch_async(units))

        assert results[0].translated_text == "Hello brave world"
        assert judge.judge_batch.call_count == 1

    def test_skips_noop_fix_when_corrected_equals_original(self) -> None:
        units = [TranslationUnit(key="k1", source_text="Same text", file_type="lang")]
        inner = _MockInner(units)
        same = "bad-Same text"
        judge = _make_judge(
            {
                "k1": Verdict(
                    verdict="flag",
                    score=2,
                    issue="grammar",
                    fix=same,
                ),
            }
        )
        progress = _RecordingProgress()
        wrapper = InlineQaWrapper(
            inner,
            judge,
            threshold=3,
            chunk_size=5,
            progress=progress,
        )

        asyncio.run(wrapper.translate_batch_async(units))

        fix_events = [e for e, _ in progress.events if e == "qa_inline_fix"]
        assert fix_events == []
        summary_events = [data for e, data in progress.events if e == "qa_inline_summary"]
        assert summary_events == [{"flagged": 1, "total": 1, "corrected": 0, "elapsed": 0.0}]

    def test_correction_events_include_reason(self) -> None:
        units = [TranslationUnit(key="k1", source_text="Hello", file_type="lang")]
        inner = _MockInner(units)
        judge = _make_judge(
            {
                "k1": Verdict(
                    verdict="flag",
                    score=1,
                    issue="meaning",
                    fix="",
                ),
            }
        )
        corrector = MagicMock()
        corrector.retranslate_with_feedback.side_effect = [
            "bad-Hello",
            "bad-Hello",
        ]
        progress = _RecordingProgress()
        wrapper = InlineQaWrapper(
            inner,
            judge,
            corrector=corrector,
            threshold=3,
            max_attempts=2,
            chunk_size=5,
            progress=progress,
        )

        asyncio.run(wrapper.translate_batch_async(units))

        corrections = [data for e, data in progress.events if e == "qa_correction"]
        assert corrections
        assert any(c.get("reason") == "unchanged" for c in corrections)

    def test_lint_gate_accepts_fix_without_russian_letters(self) -> None:
        """Judge fix that removes Russian-only letters is accepted immediately."""
        units = [TranslationUnit(key="k1", source_text="булыжник", file_type="lang")]
        inner = _MockInner(units)
        judge = _make_judge(
            {
                "k1": Verdict(
                    verdict="flag",
                    score=2,
                    issue="russism",
                    fix="бруківка",
                ),
            }
        )
        # Set target language to uk_UA on the judge mock
        judge._target_lang = "uk_UA"
        wrapper = InlineQaWrapper(
            inner,
            judge,
            threshold=3,
            chunk_size=5,
        )

        results = asyncio.run(wrapper.translate_batch_async(units))
        translated = results[0].translated_text

        # The fix should have been accepted (lint-gate), not the original text
        assert translated == "бруківка"
        # Judge should only be called once (the initial batch), not re-judged
        assert judge.judge_batch.call_count == 1

    def test_lint_gate_rejects_unchanged_russian_text(self) -> None:
        """Fix that still has Russian-only letters goes through re-judge."""
        from app.infrastructure.providers.qa_wrapper import _lint_gate_accept

        # Fix still has 'ы' → lint gate rejects (no improvement)
        assert _lint_gate_accept("булыжник", "булыжник", "uk_UA") is False
        # Fix removes Russian letter → lint gate accepts
        assert _lint_gate_accept("бруківка", "булыжник", "uk_UA") is True
        # Non-UA lang → lint gate always False
        assert _lint_gate_accept("clean", "dirty", "en_US") is False
        # Original has no Russian letters → lint gate doesn't apply
        assert _lint_gate_accept("чистий", "чистий", "uk_UA") is False

    def test_unchanged_breaks_early(self) -> None:
        """Corrector returning unchanged text stops after first attempt."""
        units = [TranslationUnit(key="k1", source_text="Hello", file_type="lang")]
        inner = _MockInner(units)
        judge = _make_judge(
            {
                "k1": Verdict(
                    verdict="flag",
                    score=1,
                    issue="meaning",
                    fix="",
                ),
            }
        )
        corrector = MagicMock()
        # Return same text every time — should stop after first attempt
        corrector.retranslate_with_feedback.side_effect = [
            "bad-Hello",  # attempt 1: unchanged
            "better-Hello",  # attempt 2: should never be called
        ]
        progress = _RecordingProgress()
        wrapper = InlineQaWrapper(
            inner,
            judge,
            corrector=corrector,
            threshold=3,
            max_attempts=3,
            chunk_size=5,
            progress=progress,
        )

        asyncio.run(wrapper.translate_batch_async(units))

        # Should only have been called once (broke on "unchanged")
        assert corrector.retranslate_with_feedback.call_count == 1
