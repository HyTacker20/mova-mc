from __future__ import annotations

from pathlib import Path

from app.core.config_loader import (
    find_config_file,
    generate_config_template,
    load_config,
)


class TestFindConfigFile:
    def test_explicit_path_found(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text("[translation]\nsource = 'en_US'\n", encoding="utf-8")
        result = find_config_file(".", explicit_path=str(config))
        assert result == config

    def test_explicit_path_not_found(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.toml"
        result = find_config_file(".", explicit_path=str(missing))
        assert result is None

    def test_found_in_mods_path(self, tmp_path: Path):
        mods = tmp_path / "mods"
        mods.mkdir()
        config = mods / "movamc.toml"
        config.write_text("[translation]\nsource = 'en_US'\n", encoding="utf-8")
        result = find_config_file(str(mods))
        assert result == config

    def test_found_in_cwd(self, tmp_path: Path, monkeypatch):
        config = tmp_path / "movamc.toml"
        config.write_text("[translation]\nsource = 'en_US'\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = find_config_file(".")
        assert result == config

    def test_found_hidden_config(self, tmp_path: Path, monkeypatch):
        config = tmp_path / ".movamc.toml"
        config.write_text("[translation]\nsource = 'en_US'\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = find_config_file(".")
        assert result == config

    def test_not_found(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = find_config_file(".")
        assert result is None

    def test_mods_path_same_as_cwd_no_duplicate(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = tmp_path / ".movamc.toml"
        config.write_text("[translation]\nsource = 'en_US'\n", encoding="utf-8")
        result = find_config_file(str(tmp_path))
        assert result == config


class TestLoadConfig:
    def test_valid_keys(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text(
            '[translation]\nsource = "uk_UA"\ntarget = "de_DE"\nprovider = "openai"\nworkers = 10\noutput = "./out"\n',
            encoding="utf-8",
        )
        result = load_config(config)
        assert result == {
            "source": "uk_UA",
            "target": "de_DE",
            "provider": "openai",
            "workers": 10,
            "output": "./out",
        }

    def test_partial_config(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text('[translation]\nsource = "uk_UA"\nworkers = 8\n', encoding="utf-8")
        result = load_config(config)
        assert result == {"source": "uk_UA", "workers": 8}

    def test_workers_as_int_parsed_from_string(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text("[translation]\nworkers = 10\n", encoding="utf-8")
        result = load_config(config)
        assert result["workers"] == 10
        assert isinstance(result["workers"], int)

    def test_unknown_keys_warned_and_skipped(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text('[translation]\nsource = "uk_UA"\nfoo = "bar"\n', encoding="utf-8")

        from loguru import logger

        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")

        result = load_config(config)
        logger.remove(sink_id)

        assert result == {"source": "uk_UA"}
        assert any("Unknown config key" in m for m in captured)

    def test_empty_config(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text("[translation]\n", encoding="utf-8")
        result = load_config(config)
        assert result == {}

    def test_no_translation_section(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text('[other]\nkey = "value"\n', encoding="utf-8")
        result = load_config(config)
        assert result == {}

    def test_workers_wrong_type_warns(self, tmp_path: Path):
        config = tmp_path / "movamc.toml"
        config.write_text('[translation]\nworkers = "ten"\n', encoding="utf-8")

        from loguru import logger

        captured: list[str] = []
        sink_id = logger.add(lambda msg: captured.append(str(msg).strip()), level="WARNING", format="{message}")

        result = load_config(config)
        logger.remove(sink_id)

        assert "workers" not in result
        assert any("must be an integer" in m for m in captured)


class TestGenerateConfigTemplate:
    def test_creates_file(self, tmp_path: Path):
        path = generate_config_template(str(tmp_path))
        assert path.exists()
        assert path.name == "movamc.toml"

    def test_content_has_expected_sections(self, tmp_path: Path):
        path = generate_config_template(str(tmp_path))
        content = path.read_text(encoding="utf-8")
        assert "[translation]" in content
        assert "source" in content
        assert "provider" in content
        assert "workers" in content

    def test_creates_parent_dirs(self, tmp_path: Path):
        out = tmp_path / "deep" / "nested"
        path = generate_config_template(str(out))
        assert path.exists()
