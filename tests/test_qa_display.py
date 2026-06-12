"""Tests for QA score display and file-log formatting."""

from __future__ import annotations

from app.domain.qa_display import (
    format_provider_model,
    format_qa_correction_line,
    format_qa_key,
    format_text_change_preview,
    strip_mc_formatting,
    truncate_preview,
)
from app.infrastructure.providers.judge import Verdict, display_score
from app.utils.qa_log import format_qa_event, log_qa_event


class TestFormatQaKey:
    def test_last_segment_when_distinctive(self) -> None:
        assert format_qa_key("info.actuallyadditions.gui.respectModInfo") == "respectModInfo"

    def test_parent_for_numeric_suffix(self) -> None:
        assert format_qa_key("booklet.actuallyadditions.trials.empoweredOil.text.1") == "text.1"

    def test_parent_for_generic_name_suffix(self) -> None:
        assert format_qa_key("item.actuallyadditions.coffee.name") == "coffee.name"


class TestStripMcFormatting:
    def test_removes_item_tags(self) -> None:
        text = "<item>Біо-Маша<r> текст"
        assert strip_mc_formatting(text) == "Біо-Маша текст"


class TestTruncatePreview:
    def test_short_text_unchanged(self) -> None:
        assert truncate_preview("hello", 80) == "hello"

    def test_long_text_truncated(self) -> None:
        result = truncate_preview("a" * 100, 20)
        assert result.endswith("…")
        assert len(result) == 20


class TestFormatTextChangePreview:
    def test_strips_tags_and_quotes(self) -> None:
        line = format_text_change_preview("<item>Old<r>", "<item>New<r>")
        assert line == '"Old" → "New"'


class TestFormatProviderModel:
    def test_strips_duplicate_provider_prefix(self) -> None:
        assert format_provider_model("ollama", "ollama/translategemma:12b") == (
            "ollama/translategemma:12b"
        )

    def test_joins_when_model_has_no_prefix(self) -> None:
        assert format_provider_model("openai", "gpt-4o-mini") == "openai/gpt-4o-mini"

    def test_model_only_when_provider_empty(self) -> None:
        assert format_provider_model("", "ollama/translategemma:12b") == "ollama/translategemma:12b"


class TestFormatQaCorrectionLine:
    def test_judge_fix_at_attempt_zero(self) -> None:
        line = format_qa_correction_line(
            key="bbw.hover.fluidmode.stopat",
            accepted=True,
            attempt=0,
            max_attempts=2,
        )
        assert line == "  ✓ stopat: judge fix applied"

    def test_retranslate_attempt(self) -> None:
        line = format_qa_correction_line(
            key="item.test",
            accepted=True,
            attempt=1,
            max_attempts=2,
        )
        assert line == "  ✓ test · attempt 1/2"

    def test_rejected_with_reason(self) -> None:
        line = format_qa_correction_line(
            key="item.coffee.name",
            accepted=False,
            attempt=2,
            max_attempts=3,
            reason="unchanged",
        )
        assert line == "  ✗ coffee.name · attempt 2/3 — unchanged"


class TestDisplayScore:
    def test_ok_without_score_defaults_to_five(self) -> None:
        assert display_score(Verdict(verdict="ok")) == 5

    def test_flag_with_score_returns_score(self) -> None:
        assert display_score(Verdict(verdict="flag", score=3)) == 3

    def test_flag_without_score_defaults_to_one(self) -> None:
        assert display_score(Verdict(verdict="flag")) == 1


class TestFormatQaEvent:
    # ── qa_verdict (flagged entries) ──

    def test_verdict_ok_not_logged(self) -> None:
        line = format_qa_event(
            "qa_verdict",
            key="bbw.key.category",
            score=5,
            is_flagged=False,
        )
        assert line is None

    def test_verdict_flagged_multi_line_with_context(self) -> None:
        line = format_qa_event(
            "qa_verdict",
            key="bbw.chat.mode.eastwest",
            is_flagged=True,
            issue="russism",
            source="East/West mode",
            translated="Схід/Західний режим",
            why="невірний рід прикметника",
        )
        assert line is not None
        assert "── ⚠" in line
        assert "russism" in line
        assert 'src:  "East/West mode"' in line
        assert 'tgt:  "Схід/Західний режим"' in line
        assert "why:  невірний рід прикметника" in line
        assert "\n" in line

    def test_verdict_flagged_minimal_no_why(self) -> None:
        line = format_qa_event(
            "qa_verdict",
            key="item.test",
            is_flagged=True,
            issue="grammar",
        )
        assert line is not None
        assert "── ⚠ test · grammar ──" in line
        # No source/translated passed — should not crash
        assert "src:" not in line
        # Fallback why is generated from the issue category
        assert "why:  grammatical error" in line

    # ── qa_inline_judging ──

    def test_inline_judging(self) -> None:
        line = format_qa_event("qa_inline_judging", count=5, chunk_size=5)
        assert line == "→ judging 5 item(s)…"

    # ── qa_inline_summary ──

    def test_inline_summary_skips_empty_batch(self) -> None:
        line = format_qa_event(
            "qa_inline_summary",
            flagged=0,
            total=25,
            corrected=0,
            elapsed=0.0,
        )
        assert line is None

    def test_inline_summary_with_flags(self) -> None:
        line = format_qa_event(
            "qa_inline_summary",
            flagged=1,
            total=5,
            corrected=1,
            elapsed=7.9,
        )
        assert line == "← batch · 1/5 flagged, 1 corrected (7.9s)"

    # ── qa_inline_status ──

    def test_inline_status_uses_message(self) -> None:
        line = format_qa_event(
            "qa_inline_status",
            message="Inline QA · openai/deepseek-v4-flash",
        )
        assert line == "Inline QA · openai/deepseek-v4-flash"

    # ── qa_inline_fix (multi-line) ──

    def test_inline_fix_multi_line_with_context(self) -> None:
        line = format_qa_event(
            "qa_inline_fix",
            key="item.coffee.name",
            source="Coffee Dust",
            original="<item>Біо-Маша<r>",
            fixed="<item>Біомасу<r>",
            issue="russism",
            why="використано російське слово 'Маша'",
        )
        assert line is not None
        assert "\n" in line
        assert "── ✓ coffee.name · fix applied ──" in line
        assert 'src:  "Coffee Dust"' in line
        assert 'was:  "Біо-Маша"' in line
        assert 'now:  "Біомасу"' in line
        assert "flag: russism" in line
        assert "why:  використано російське слово" in line

    def test_inline_fix_minimal_no_source_no_why(self) -> None:
        line = format_qa_event(
            "qa_inline_fix",
            key="item.test",
            original="Old text",
            fixed="New text",
        )
        assert line is not None
        assert "── ✓ test · fix applied ──" in line
        assert 'was:  "Old text"' in line
        assert 'now:  "New text"' in line
        assert "src:" not in line  # no source passed
        assert "why:" not in line  # no why passed

    # ── qa_correction (multi-line) ──

    def test_correction_simple_judge_fix_suppressed(self) -> None:
        # Simple judge fixes are suppressed — qa_inline_fix follows with full context
        line = format_qa_event(
            "qa_correction",
            key="item.coffee.name",
            accepted=True,
            attempt=0,
            max_attempts=3,
        )
        assert line is None

    def test_correction_with_reason_and_change(self) -> None:
        line = format_qa_event(
            "qa_correction",
            key="item.coffee.name",
            accepted=False,
            attempt=2,
            max_attempts=3,
            reason="unchanged",
            original="Old text",
            corrected="Old text",
            why="corrector returned identical text",
        )
        assert "fix unchanged" in line
        # "unchanged" becomes the verb in the header line
        assert "unchanged" in line.split("\n")[0]

    def test_correction_rejected_with_reason(self) -> None:
        line = format_qa_event(
            "qa_correction",
            key="item.test",
            accepted=False,
            attempt=1,
            max_attempts=3,
            reason="re-judge rejected",
            original="Original",
            why="пилюка — нестандартний термін",
        )
        assert "✗" in line
        assert "attempt 1/3" in line
        assert "re-judge rejected" in line
        assert "why:  пилюка" in line

    # ── qa_done ──

    def test_qa_done_has_separator(self) -> None:
        line = format_qa_event("qa_done", flagged=8, corrected=3)
        assert line is not None
        assert line.startswith("\n── ✓ QA done")
        assert "8 flagged" in line
        assert "3 corrected" in line

    # ── edge cases ──

    def test_unknown_event_returns_none(self) -> None:
        assert format_qa_event("qa_unknown") is None


class TestLogQaEvent:
    def test_ok_verdict_not_logged(self) -> None:
        captured: list[str] = []

        from loguru import logger

        sink_id = logger.add(
            lambda msg: captured.append(str(msg).strip()),
            level="INFO",
            format="{message}",
        )
        try:
            log_qa_event(
                "qa_verdict",
                key="item.test",
                score=5,
                is_flagged=False,
            )
        finally:
            logger.remove(sink_id)

        assert captured == []

    def test_skips_unknown_events(self) -> None:
        captured: list[str] = []

        from loguru import logger

        sink_id = logger.add(
            lambda msg: captured.append(str(msg).strip()),
            level="INFO",
            format="{message}",
        )
        try:
            log_qa_event("qa_unknown")
        finally:
            logger.remove(sink_id)

        assert captured == []
