"""Tests for QA score display and file-log formatting."""

from __future__ import annotations

from app.domain.qa_display import format_provider_model, format_qa_correction_line
from app.infrastructure.providers.judge import Verdict, display_score
from app.utils.qa_log import format_qa_event, log_qa_event


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
        assert line == "  ✓ bbw.hover.fluidmode.stopat: judge fix applied"

    def test_retranslate_attempt(self) -> None:
        line = format_qa_correction_line(
            key="item.test",
            accepted=True,
            attempt=1,
            max_attempts=2,
        )
        assert line == "  ✓ 1/2 item.test"


class TestDisplayScore:
    def test_ok_without_score_defaults_to_five(self) -> None:
        assert display_score(Verdict(verdict="ok")) == 5

    def test_flag_with_score_returns_score(self) -> None:
        assert display_score(Verdict(verdict="flag", score=3)) == 3

    def test_flag_without_score_defaults_to_one(self) -> None:
        assert display_score(Verdict(verdict="flag")) == 1


class TestFormatQaEvent:
    def test_verdict_ok_not_logged(self) -> None:
        line = format_qa_event(
            "qa_verdict",
            key="bbw.key.category",
            score=5,
            is_flagged=False,
        )
        assert line is None

    def test_verdict_flagged_with_issue(self) -> None:
        line = format_qa_event(
            "qa_verdict",
            key="bbw.chat.mode.eastwest",
            score=3,
            is_flagged=True,
            issue="russism",
        )
        assert line == "  ⚠ bbw.chat.mode.eastwest: scored 3/5 — russism"

    def test_inline_judging(self) -> None:
        line = format_qa_event("qa_inline_judging", count=5, chunk_size=5)
        assert line == "→ judging 5 item(s) (chunk=5)"

    def test_inline_summary(self) -> None:
        line = format_qa_event(
            "qa_inline_summary",
            flagged=1,
            total=5,
            corrected=1,
            elapsed=7.9,
        )
        assert line == "← 1/5 flagged, 1/1 corrected (7.9s)"

    def test_inline_status_no_duplicate_provider(self) -> None:
        line = format_qa_event(
            "qa_inline_status",
            provider="ollama",
            model="ollama/translategemma:12b",
        )
        assert line == "───── Inline QA active (ollama/translategemma:12b) ─────"

    def test_correction_judge_fix(self) -> None:
        line = format_qa_event(
            "qa_correction",
            key="bbw.hover.fluidmode.stopat",
            accepted=True,
            attempt=0,
            max_attempts=2,
        )
        assert line == "  ✓ bbw.hover.fluidmode.stopat: judge fix applied"

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
