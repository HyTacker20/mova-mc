"""Tests for judge prompt templates."""

from __future__ import annotations

import re

from app.infrastructure.providers.judge_prompts import (
    JUDGE_PROMPT_VERSION,
    make_feedback_user_prompt,
    make_judge_prompt,
)


def test_judge_prompt_version_format() -> None:
    assert re.fullmatch(r"\d+\.\d+", JUDGE_PROMPT_VERSION)


def test_make_judge_prompt_fills_langs() -> None:
    prompt = make_judge_prompt("English", "Ukrainian")
    assert "English" in prompt
    assert "Ukrainian" in prompt


def test_make_judge_prompt_appends_glossary() -> None:
    prompt = make_judge_prompt("English", "Ukrainian", glossary_terms="Use this terminology: stone→Камень.")
    assert "Use this terminology: stone→Камень." in prompt


def test_make_judge_prompt_no_glossary() -> None:
    prompt = make_judge_prompt("English", "Ukrainian")
    assert "Use this terminology" not in prompt


def test_make_feedback_user_prompt_contains_all_parts() -> None:
    prompt = make_feedback_user_prompt(
        source_lang="English",
        target_lang="Ukrainian",
        src="Stone pickaxe",
        prev_tgt="Кам'яний кирка",
        issue="grammar",
        why="рід не узгоджено",
    )
    assert "English" in prompt
    assert "Ukrainian" in prompt
    assert "Stone pickaxe" in prompt
    assert "Кам'яний кирка" in prompt
    assert "grammar" in prompt
    assert "рід не узгоджено" in prompt


def test_make_judge_prompt_injects_ru_uk_rules() -> None:
    """ru→uk pair gets the language-specific anti-russism rules."""
    prompt = make_judge_prompt("Russian", "Ukrainian")
    assert "ru→uk specific rules" in prompt
    assert "RUSSIAN-ONLY LETTERS" in prompt
    assert "WHEN WRITING A FIX" in prompt
    assert "DO NOT FALSE-FLAG" in prompt


def test_make_judge_prompt_no_lang_rules_for_unrelated_pair() -> None:
    """en→es pair should NOT get ru→uk rules."""
    prompt = make_judge_prompt("English", "Spanish")
    assert "ru→uk specific rules" not in prompt


def test_make_judge_prompt_lang_rules_with_glossary() -> None:
    """Lang-specific rules are injected BEFORE glossary snippet."""
    prompt = make_judge_prompt(
        "Russian", "Ukrainian", glossary_terms="Use this terminology: Cobblestone→Бруківка."
    )
    rules_pos = prompt.index("ru→uk specific rules")
    glossary_pos = prompt.index("Use this terminology")
    assert rules_pos < glossary_pos
