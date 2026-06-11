import argparse

import pytest

from app.core.settings import Settings
from app.infrastructure.parsers.json_parser import parse_json_with_comments, remove_comments_from_json
from app.interfaces.cli.args import add_translate_arguments


class TestSettings:
    def test_default_values(self):
        import tempfile as _tempfile

        settings = Settings()
        assert settings.source_mc_lang == "en_US"
        assert settings.target_mc_lang == "es_ES"
        assert settings.mods_path == "./"
        # Default temp_path is a unique dir under the system temp directory
        assert settings.temp_path.startswith(_tempfile.gettempdir())
        assert "mmt_" in settings.temp_path
        assert settings.translation_path == "./translated_mods"
        assert settings.provider == "google"

    def test_cli_args_override(self):
        args = argparse.Namespace(
            source="uk_UA",
            target="de_DE",
            path="./my_mods",
            output="./my_output",
            provider="openai",
        )
        settings = Settings(cli_args=args)
        assert settings.source_mc_lang == "uk_UA"
        assert settings.target_mc_lang == "de_DE"
        assert settings.mods_path == "./my_mods"
        assert settings.translation_path == "./my_output"
        assert settings.provider == "openai"

    def test_google_lang_extraction(self):
        settings = Settings()
        assert settings.source_google_lang == "en"
        assert settings.target_google_lang == "es"

    def test_format_lang(self):
        settings = Settings()
        result = settings._format_lang("UK_ua")
        assert result == "uk_UA"

    def test_format_lang_single_part(self):
        settings = Settings()
        result = settings._format_lang("en")
        assert result == "en"

    def test_format_lang_empty_string(self):
        settings = Settings()
        result = settings._format_lang("")
        assert result == ""

    def test_add_translate_arguments(self):
        parser = argparse.ArgumentParser()
        add_translate_arguments(parser)
        args = parser.parse_args(["-p", "./mods", "-s", "en_US", "-t", "uk_UA", "--provider", "openai"])
        assert args.path == "./mods"
        assert args.source == "en_US"
        assert args.target == "uk_UA"
        assert args.provider == "openai"

    def test_config_data_overrides_defaults(self):
        config = {"source": "uk_UA", "target": "de_DE", "provider": "openai", "workers": 10, "output": "./my_out"}
        settings = Settings(config_data=config)
        assert settings.source_mc_lang == "uk_UA"
        assert settings.target_mc_lang == "de_DE"
        assert settings.provider == "openai"
        assert settings.max_workers == 10
        assert settings.translation_path == "./my_out"

    def test_cli_overrides_config_data(self):
        config = {"source": "uk_UA", "provider": "openai", "workers": 10}
        args = argparse.Namespace(source="fr_FR", provider="google", workers=5)
        settings = Settings(cli_args=args, config_data=config)
        assert settings.source_mc_lang == "fr_FR"
        assert settings.provider == "google"
        assert settings.max_workers == 5

    def test_config_data_partial(self):
        config = {"source": "uk_UA"}
        settings = Settings(config_data=config)
        assert settings.source_mc_lang == "uk_UA"
        assert settings.target_mc_lang == "es_ES"
        assert settings.provider == "google"
        assert settings.max_workers == 4

    def test_config_with_no_cli_args(self):
        config = {"source": "de_DE", "provider": "anthropic"}
        settings = Settings(config_data=config)
        assert settings.source_mc_lang == "de_DE"
        assert settings.provider == "anthropic"

    def test_config_empty_dict_no_change(self):
        settings = Settings(config_data={})
        assert settings.source_mc_lang == "en_US"
        assert settings.provider == "google"

    def test_config_none_no_change(self):
        settings = Settings(config_data=None)
        assert settings.source_mc_lang == "en_US"
        assert settings.provider == "google"


class TestJsonParsing:
    def test_remove_comments_single_line(self):
        content = '{"key": "value"} // comment'
        result = remove_comments_from_json(content)
        assert "comment" not in result

    def test_remove_comments_multi_line(self):
        content = '{"key": /* block comment */ "value"}'
        result = remove_comments_from_json(content)
        assert "block comment" not in result

    def test_parse_json_with_comments(self, tmp_path, sample_json_with_comments):
        path = tmp_path / "test.json"
        path.write_text(sample_json_with_comments, encoding="utf-8")
        result = parse_json_with_comments(str(path))
        assert result["item.minecraft.diamond"] == "Diamond"
        assert result["item.minecraft.gold_ingot"] == "Gold Ingot"

    def test_parse_json_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        from app.exceptions import FileParsingError

        with pytest.raises(FileParsingError):
            parse_json_with_comments(str(path))
