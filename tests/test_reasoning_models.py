"""Tests for per-model reasoning/thinking policy."""

from __future__ import annotations

from app.infrastructure.providers.reasoning_models import (
    ReasoningTask,
    build_extra_body,
    is_deepseek_v4,
    scale_max_tokens,
    strip_thinking_artifacts,
)


class TestModelDetection:
    def test_deepseek_v4_flash(self) -> None:
        assert is_deepseek_v4("deepseek-v4-flash")
        assert is_deepseek_v4("opencode-go/deepseek-v4-flash")

    def test_non_deepseek(self) -> None:
        assert not is_deepseek_v4("glm-5.1")


class TestBuildExtraBody:
    def test_deepseek_disables_thinking(self) -> None:
        assert build_extra_body("deepseek-v4-flash") == {"thinking": {"type": "disabled"}}

    def test_glm_returns_none(self) -> None:
        assert build_extra_body("glm-5.1") is None

    def test_judge_task_same_for_deepseek(self) -> None:
        assert build_extra_body("deepseek-v4-pro", task=ReasoningTask.JUDGE) == {
            "thinking": {"type": "disabled"},
        }


class TestScaleMaxTokens:
    def test_deepseek_unchanged(self) -> None:
        assert scale_max_tokens("deepseek-v4-flash", 1024) == 1024

    def test_glm_bumped(self) -> None:
        assert scale_max_tokens("glm-5.1", 1024) == 8192

    def test_mimo_unchanged(self) -> None:
        assert scale_max_tokens("mimo-v2.5", 1000) == 1000


class TestStripThinkingArtifacts:
    def test_redacted_thinking(self) -> None:
        raw = "<think>secret</think>\nПривіт"
        assert strip_thinking_artifacts(raw) == "Привіт"

    def test_think_tags(self) -> None:
        raw = "\x3cthink\x3e\nmulti\nline\n\x3c/think\x3eВідповідь"
        assert strip_thinking_artifacts(raw) == "Відповідь"

    def test_uppercase_think_block(self) -> None:
        raw = "<THINK>only</THINK>Answer"
        assert strip_thinking_artifacts(raw) == "Answer"
