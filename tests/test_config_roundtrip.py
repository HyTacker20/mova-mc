"""Tests for config round-trip: save_config → load_config preserves all keys."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config_loader import load_config, save_config


class TestConfigRoundTrip:
    """Verify that save_config/load_config round-trips all supported keys."""

    @pytest.fixture
    def config_dir(self, tmp_path: Path) -> Path:
        path = tmp_path / "config_test"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_round_trip_basic_keys(self, config_dir: Path) -> None:
        """Basic translation keys survive round-trip."""
        data = {
            "source": "en_US",
            "target": "uk_UA",
            "provider": "openai",
            "workers": 8,
            "translation_path": "./output",
            "output_mode": "separate",
        }
        saved = save_config(data, config_dir / "movamc.toml")
        loaded = load_config(saved)
        assert loaded["source"] == "en_US"
        assert loaded["target"] == "uk_UA"
        assert loaded["provider"] == "openai"
        assert loaded["workers"] == 8
        assert loaded["output"] == "./output"
        assert loaded["output_mode"] == "separate"

    def test_round_trip_advanced_keys(self, config_dir: Path) -> None:
        """Advanced keys (hint_lang, glossary, no_cache) survive round-trip."""
        data = {
            "source": "fr_FR",
            "target": "de_DE",
            "provider": "google",
            "hint_lang": "en_US",
            "glossary_path": "/path/to/glossary.json",
            "no_cache": True,
            "workers": 4,
            "output_mode": "replace",
        }
        saved = save_config(data, config_dir / "movamc.toml")
        loaded = load_config(saved)
        assert loaded["hint_lang"] == "en_US"
        assert loaded["glossary_path"] == "/path/to/glossary.json"
        assert loaded["no_cache"] is True

    def test_round_trip_minimal(self, config_dir: Path) -> None:
        """Minimal data round-trips without errors."""
        data = {"source": "en_US", "target": "es_ES", "provider": "google"}
        saved = save_config(data, config_dir / "movamc.toml")
        loaded = load_config(saved)
        assert loaded["source"] == "en_US"
        assert loaded["target"] == "es_ES"

    def test_round_trip_mods_section(self, config_dir: Path) -> None:
        """Mods include/exclude patterns survive round-trip."""
        data = {
            "source": "en_US",
            "target": "pl_PL",
            "provider": "google",
            "mods": {"include": ["*"], "exclude": ["test_*"]},
        }
        saved = save_config(data, config_dir / "movamc.toml")
        loaded = load_config(saved)
        assert "mods" in loaded
        assert loaded["mods"]["include"] == ["*"]
        assert loaded["mods"]["exclude"] == ["test_*"]

    def test_empty_output_mode_handled(self, config_dir: Path) -> None:
        """Empty translation_path doesn't pollute config."""
        data = {
            "source": "en_US",
            "target": "it_IT",
            "provider": "google",
            "output_mode": "replace",
        }
        saved = save_config(data, config_dir / "movamc.toml")
        loaded = load_config(saved)
        assert loaded.get("output_mode") == "replace"

    def test_qa_table_alias_keys(self) -> None:
        """Web API alias keys (enabled/provider/model) parse via from_dict."""
        from app.core.qa_config import QaConfig

        qa = QaConfig.from_dict(
            {
                "enabled": True,
                "provider": "opencode",
                "model": "deepseek-v4-flash",
            },
            flat=False,
        )
        assert qa.enabled is True
        assert qa.provider == "opencode"
        assert qa.model == "deepseek-v4-flash"

    def test_round_trip_qa_corrector_model(self, config_dir: Path) -> None:
        """QA corrector_model survives round-trip."""
        data = {
            "source": "en_US",
            "target": "uk_UA",
            "provider": "openai",
            "qa_corrector_model": "gpt-4o-mini",
        }
        saved = save_config(data, config_dir / "movamc.toml")
        loaded = load_config(saved)
        assert loaded["qa"]["corrector_model"] == "gpt-4o-mini"

        from app.core.settings import Settings

        settings = Settings(config_data=loaded)
        assert settings.qa.corrector_model == "gpt-4o-mini"

    def test_round_trip_ui_locale(self, config_dir: Path) -> None:
        """UI locale survives round-trip in [translation] section."""
        data = {
            "source": "en_US",
            "target": "uk_UA",
            "provider": "google",
            "ui_locale": "uk",
        }
        saved = save_config(data, config_dir / "movamc.toml")
        loaded = load_config(saved)
        assert loaded["ui_locale"] == "uk"
