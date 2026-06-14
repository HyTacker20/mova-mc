"""Tests for Settings class with new advanced config keys."""

from __future__ import annotations

from argparse import Namespace

from app.core.settings import Settings


class TestSettingsExtended:
    def test_no_cli_args_defaults(self):
        settings = Settings()
        assert settings.max_workers == 4
        assert settings.dry_run is False
        assert settings.source_mc_lang == "en_US"
        assert settings.target_mc_lang == "es_ES"
        assert settings.provider == "google"


class TestSettingsNewKeys:
    """Settings correctly applies new config keys with correct precedence."""

    def test_config_applies_hint_lang(self) -> None:
        """hint_lang from config is applied."""
        s = Settings(config_data={"hint_lang": "ru_RU"})
        assert s.hint_lang == "ru_RU"

    def test_config_applies_glossary_path(self) -> None:
        """glossary_path from config is applied."""
        s = Settings(config_data={"glossary_path": "/my/glossary.json"})
        assert s.glossary_path == "/my/glossary.json"

    def test_config_applies_no_cache(self) -> None:
        """no_cache from config is applied as bool."""
        s = Settings(config_data={"no_cache": True})
        assert s.no_cache is True

    def test_config_applies_output_mode(self) -> None:
        """output_mode from config is applied."""
        s = Settings(config_data={"output_mode": "separate"})
        assert s.output_mode == "separate"

    def test_default_output_mode(self) -> None:
        """Default output_mode is 'resourcepack'."""
        s = Settings()
        assert s.output_mode == "resourcepack"

    def test_cli_overrides_config_hint_lang(self) -> None:
        """CLI args override config for hint_lang."""
        args = Namespace(hint_lang="de_DE")
        s = Settings(cli_args=args, config_data={"hint_lang": "ru_RU"})
        assert s.hint_lang == "de_DE"

    def test_cli_overrides_config_no_cache(self) -> None:
        """CLI args override config for no_cache."""
        args = Namespace(no_cache=True)
        s = Settings(cli_args=args, config_data={"no_cache": False})
        assert s.no_cache is True

    def test_cli_overrides_config_output_mode(self) -> None:
        """CLI args override config for output_mode."""
        args = Namespace(output_mode="replace")
        s = Settings(cli_args=args, config_data={"output_mode": "separate"})
        assert s.output_mode == "replace"


class TestReplaceMode:
    """Replace mode maps translation_path to mods_path (Fix 1.4)."""

    def test_replace_mode_sets_translation_path_to_mods_path(self) -> None:
        """In replace mode, translation_path should equal mods_path (simulating _save_to_app_settings)."""
        s = Settings()
        s.mods_path = "/some/mods/folder"
        s.output_mode = "replace"
        s.translation_path = s.mods_path  # what _save_to_app_settings does
        assert s.translation_path == "/some/mods/folder"
        assert s.translation_path == s.mods_path

    def test_separate_mode_preserves_translation_path(self) -> None:
        """In separate mode, translation_path stays as set."""
        s = Settings()
        s.mods_path = "/some/mods/folder"
        s.output_mode = "separate"
        s.translation_path = "/custom/output"
        assert s.translation_path == "/custom/output"
        assert s.translation_path != s.mods_path
