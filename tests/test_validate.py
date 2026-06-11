"""Tests for the validate pipeline stage."""

from unittest.mock import MagicMock

from app.application.stages.validate import _validate_result
from app.domain.models import TranslationResult, TranslationUnit
from app.utils.progress import ProgressReporter


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.progress = ProgressReporter()
    return ctx


def _result(translated_text: str, **kwargs) -> TranslationResult:
    defaults = {
        "unit": TranslationUnit(key="k", source_text="source", file_type="json"),
        "translated_text": translated_text,
        "success": True,
    }
    defaults.update(kwargs)
    return TranslationResult(**defaults)


class TestValidatePreservesQaFields:
    def test_qa_judge_fields_kept_when_lint_warnings_added(self) -> None:
        validated = _validate_result(
            _result(
                "ёлка",
                qa_score=2,
                qa_issue="russism",
                qa_attempts=1,
            ),
            ctx=_mock_ctx(),
            run_uk_lint=True,
        )

        assert validated.qa_score == 2
        assert validated.qa_issue == "russism"
        assert validated.qa_attempts == 1
        assert len(validated.qa_warnings) >= 1

    def test_unchanged_when_no_warnings(self) -> None:
        original = _result(
            "Привіт",
            qa_score=4,
            qa_issue=None,
            qa_attempts=0,
        )
        validated = _validate_result(original, ctx=_mock_ctx(), run_uk_lint=True)

        assert validated is original
