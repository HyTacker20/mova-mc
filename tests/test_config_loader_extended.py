"""Extended tests for config_loader — edge cases, mods, QA, rate_limit sections."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config_loader import (
    CONFIG_FILE_NAME,
    _fmt_val,
    _log_config_delta,
    generate_config_template,
    load_config,
    save_config,
)


class TestLoadConfigEdgeCases:
    def test_translation_section_not_a_table(self, tmp_path: Path) -> None:
        """When [translation] is a scalar instead of a table, returns {}."""
        config = tmp_path / "movamc.toml"
        config.write_text("translation = 42\n", encoding="utf-8")
        result = load_config(config)
        assert result == {}

    def test_chunk_size_type_error(self, tmp_path: Path) -> None:
        """Non-integer chunk_size is warned and skipped."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\nchunk_size = "abc"\n', encoding="utf-8"
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert "chunk_size" not in result
        assert any("must be an integer" in m for m in captured)

    def test_chunk_token_budget_type_error(self, tmp_path: Path) -> None:
        """Non-integer chunk_token_budget is warned and skipped."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\nchunk_token_budget = "large"\n', encoding="utf-8"
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert "chunk_token_budget" not in result

    def test_chunk_max_text_length_type_error(self, tmp_path: Path) -> None:
        """Non-integer chunk_max_text_length is warned and skipped."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\nchunk_max_text_length = "long"\n', encoding="utf-8"
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert "chunk_max_text_length" not in result

    def test_progress_batch_size_type_error(self, tmp_path: Path) -> None:
        """Non-integer progress_batch_size is warned and skipped."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\nprogress_batch_size = "big"\n', encoding="utf-8"
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert "progress_batch_size" not in result


class TestLoadConfigMods:
    def test_mods_include_list(self, tmp_path: Path) -> None:
        """Mods include as a list."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[mods]\ninclude = ["mod_a", "mod_b"]\n',
            encoding="utf-8",
        )
        result = load_config(config)
        assert "mods" in result
        assert result["mods"]["include"] == ["mod_a", "mod_b"]

    def test_mods_include_string(self, tmp_path: Path) -> None:
        """Mods include as a single string gets wrapped in a list."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[mods]\ninclude = "only_this_mod"\n',
            encoding="utf-8",
        )
        result = load_config(config)
        assert "mods" in result
        assert result["mods"]["include"] == ["only_this_mod"]

    def test_mods_include_non_string_or_list(self, tmp_path: Path) -> None:
        """Mods include that is neither string nor list is ignored."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[mods]\ninclude = 42\n',
            encoding="utf-8",
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert "mods" not in result
        assert any("must be a string or list" in m for m in captured)

    def test_mods_unknown_key(self, tmp_path: Path) -> None:
        """Unknown mods key is warned about."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[mods]\nunknown_key = true\n',
            encoding="utf-8",
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert any("Unknown mods config key" in m for m in captured)


class TestLoadConfigQA:
    def test_qa_section(self, tmp_path: Path) -> None:
        """QA section keys are loaded."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[qa]\njudge = true\nthreshold = 0.8\nmax_attempts = 3\n',
            encoding="utf-8",
        )
        result = load_config(config)
        assert "qa" in result
        assert result["qa"]["judge"] is True
        assert result["qa"]["threshold"] == 0.8
        assert result["qa"]["max_attempts"] == 3

    def test_qa_unknown_key(self, tmp_path: Path) -> None:
        """Unknown QA key is warned about."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[qa]\njudge = true\nnope = "bad"\n',
            encoding="utf-8",
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert any("Unknown QA config key" in m for m in captured)


class TestLoadConfigRateLimit:
    def test_rate_limit_simple(self, tmp_path: Path) -> None:
        """Simple rate_limit config keys."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[rate_limit]\nrpm = 30\nburst = 5\n',
            encoding="utf-8",
        )
        result = load_config(config)
        assert "rate_limit" in result
        assert result["rate_limit"]["rpm"] == 30
        assert result["rate_limit"]["burst"] == 5

    def test_rate_limit_service(self, tmp_path: Path) -> None:
        """Per-service rate_limit config."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[rate_limit.google]\nrpm = 10.0\nburst = 3.0\n',
            encoding="utf-8",
        )
        result = load_config(config)
        assert "rate_limit" in result
        assert "google" in result["rate_limit"]
        assert result["rate_limit"]["google"]["rpm"] == 10.0
        assert result["rate_limit"]["google"]["burst"] == 3.0

    def test_rate_limit_unknown_key(self, tmp_path: Path) -> None:
        """Unknown rate_limit top-level key is warned."""
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "en_US"\n[rate_limit]\nweird = 1\n',
            encoding="utf-8",
        )
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")
        result = load_config(config)
        logger.remove(sink_id)
        assert any("Unknown rate_limit config key" in m for m in captured)


class TestSaveConfig:
    def test_save_overwrites(self, tmp_path: Path) -> None:
        """save_config writes TOML to the target path."""
        config_path = tmp_path / "movamc.toml"
        data = {"source": "en_US", "target": "uk_UA", "provider": "openai"}
        result = save_config(data, config_path)
        assert result == config_path
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")
        assert "source" in content

    def test_save_default_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """save_config without explicit path writes to CWD."""
        monkeypatch.chdir(tmp_path)
        data = {"source": "en_US"}
        result = save_config(data)
        assert result == tmp_path / CONFIG_FILE_NAME
        assert result.exists()

    def test_save_no_changes(self, tmp_path: Path) -> None:
        """save_config logs 'no changes' when content is identical."""
        config_path = tmp_path / "movamc.toml"
        data = {"source": "en_US", "provider": "openai"}
        # First save
        save_config(data, config_path)
        # Second save with same data
        from loguru import logger
        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="INFO", format="{message}")
        save_config(data, config_path)
        logger.remove(sink_id)
        assert any("no changes" in m for m in captured)

    def test_save_mods_string_to_list(self, tmp_path: Path) -> None:
        """save_config converts single mod string to list in TOML."""
        config_path = tmp_path / "movamc.toml"
        data = {"source": "en_US", "mods": {"include": "single_mod"}}
        result = save_config(data, config_path)
        content = result.read_text(encoding="utf-8")
        assert 'include = ["single_mod"]' in content or "include = [\n" in content

    def test_save_qa_section(self, tmp_path: Path) -> None:
        """save_config preserves QA section keys."""
        config_path = tmp_path / "movamc.toml"
        data = {"source": "en_US", "qa": {"judge": True, "threshold": 0.8}}
        result = save_config(data, config_path)
        content = result.read_text(encoding="utf-8")
        assert "judge" in content

    def test_save_rate_limit(self, tmp_path: Path) -> None:
        """save_config preserves rate_limit section."""
        config_path = tmp_path / "movamc.toml"
        data = {"source": "en_US", "rate_limit": {"rpm": 30, "google": {"rpm": 10.0}}}
        result = save_config(data, config_path)
        content = result.read_text(encoding="utf-8")
        assert "[rate_limit]" in content

    def test_save_handles_corrupted_prev(self, tmp_path: Path) -> None:
        """save_config handles corrupted previous config gracefully."""
        config_path = tmp_path / "movamc.toml"
        config_path.write_text("not valid toml {{{", encoding="utf-8")
        data = {"source": "en_US"}
        # Should not raise — delta comparison falls back
        result = save_config(data, config_path)
        assert result.exists()


class TestFmtVal:
    def test_bool_true(self) -> None:
        assert _fmt_val(True) == "true"

    def test_bool_false(self) -> None:
        assert _fmt_val(False) == "false"

    def test_string(self) -> None:
        assert _fmt_val("hello") == "'hello'"

    def test_list(self) -> None:
        assert _fmt_val(["a", "b"]) == "['a', 'b']"

    def test_int(self) -> None:
        assert _fmt_val(42) == "42"

    def test_datetime(self) -> None:
        """datetime is handled via str() fallback."""
        dt = datetime(2025, 1, 15, 10, 30)
        result = _fmt_val(dt)
        assert "2025" in result
