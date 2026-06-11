from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.infrastructure.providers.glossary import (
    get_relevant_terms,
    load_merged_glossary,
    load_user_glossary,
)
from app.infrastructure.providers.openai_like import OpenAILikeProvider


class TestGetRelevantTerms:
    def test_empty_glossary_returns_empty(self):
        assert get_relevant_terms({}, ["Some Stone block"]) == ""

    def test_no_match_returns_empty(self):
        assert get_relevant_terms({"Redstone": "Редстоун"}, ["A diamond sword"]) == ""

    def test_matching_term_is_included(self):
        snippet = get_relevant_terms({"Redstone": "Редстоун"}, ["A pile of Redstone dust"])
        assert "Use this terminology" in snippet
        assert "Redstone→Редстоун" in snippet

    def test_match_is_case_insensitive(self):
        snippet = get_relevant_terms({"Redstone": "Редстоун"}, ["redstone torch"])
        assert "Redstone→Редстоун" in snippet

    def test_only_relevant_terms_included(self):
        glossary = {"Redstone": "Редстоун", "Creeper": "Кріпер"}
        snippet = get_relevant_terms(glossary, ["Redstone dust"])
        assert "Redstone" in snippet
        assert "Creeper" not in snippet


class TestUserGlossary:
    def test_load_user_glossary_none(self):
        assert load_user_glossary(None) == {}

    def test_load_user_glossary_missing_file(self, tmp_path: Path):
        assert load_user_glossary(str(tmp_path / "nope.json")) == {}

    def test_load_user_glossary_reads_pairs(self, tmp_path: Path):
        p = tmp_path / "g.json"
        p.write_text(json.dumps({"Foo": "Бар"}), encoding="utf-8")
        assert load_user_glossary(str(p)) == {"Foo": "Бар"}

    def test_load_user_glossary_ignores_non_string_values(self, tmp_path: Path):
        p = tmp_path / "g.json"
        p.write_text(json.dumps({"Foo": "Бар", "Bad": 1}), encoding="utf-8")
        assert load_user_glossary(str(p)) == {"Foo": "Бар"}

    def test_builtin_glossary_is_optional(self):
        # An unknown language has no built-in file and no user file → empty.
        assert load_merged_glossary("xx_YY", None) == {}

    def test_user_entries_take_precedence(self, tmp_path: Path):
        p = tmp_path / "g.json"
        p.write_text(json.dumps({"Stone": "МійКамінь"}), encoding="utf-8")
        merged = load_merged_glossary("uk_UA", str(p))
        assert merged["Stone"] == "МійКамінь"


def _make_provider(glossary: dict[str, str] | None) -> OpenAILikeProvider:
    transport = MagicMock()
    transport.complete.return_value = "переклад"
    return OpenAILikeProvider(
        source_lang="en_US",
        target_lang="uk_UA",
        transport=transport,
        capitalize=False,
        max_retries=0,
        chunk_size=0,
        source_lang_display="English",
        target_lang_display="Ukrainian",
        glossary=glossary,
    )


class TestProviderGlossaryInjection:
    def test_glossary_terms_injected_into_system_prompt(self):
        p = _make_provider({"Redstone": "Редстоун"})
        p.translate("Redstone dust")
        system_prompt = p._transport.complete.call_args.args[0][0]["content"]
        assert "Use this terminology" in system_prompt
        assert "Редстоун" in system_prompt

    def test_empty_glossary_adds_no_terminology_line(self):
        p = _make_provider({})
        p.translate("Redstone dust")
        system_prompt = p._transport.complete.call_args.args[0][0]["content"]
        assert "Use this terminology" not in system_prompt

    def test_display_names_used_in_prompt(self):
        # Guards that human-readable language names reach the prompt.
        p = _make_provider({})
        p.translate("hello")
        system_prompt = p._transport.complete.call_args.args[0][0]["content"]
        assert "English" in system_prompt
        assert "Ukrainian" in system_prompt


class TestFactoryForwarding:
    def test_get_translator_service_forwards_display_and_glossary(self, monkeypatch):
        import app.infrastructure.providers.registry as registry
        import app.infrastructure.providers.factory as factory

        captured: dict[str, object] = {}

        def fake_build(provider: str, **kwargs: object) -> object:
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(registry, "_build_openai_like", fake_build)

        factory.get_translator_service(
            provider="litellm",
            source_lang="en_US",
            target_lang="uk_UA",
            source_lang_display="English",
            target_lang_display="Ukrainian",
            glossary={"Redstone": "Редстоун"},
        )

        assert captured["source_lang_display"] == "English"
        assert captured["target_lang_display"] == "Ukrainian"
        assert captured["glossary"] == {"Redstone": "Редстоун"}
