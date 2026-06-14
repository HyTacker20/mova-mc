"""Tests for lang_discovery.py — discover_lang_files and _discover_mcfunction_folders."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.filesystem.lang_discovery import (
    _discover_mcfunction_folders,
    discover_lang_files,
)


class TestDiscoverLangFiles:
    def test_finds_lang_folder(self, tmp_path: Path) -> None:
        """Finds en_us.json inside a standard assets/mod/lang/ structure."""
        lang_dir = tmp_path / "mod1" / "assets" / "testmod" / "lang"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en_us.json").write_text('{"key": "value"}')

        folders = discover_lang_files(tmp_path, "en_us")
        assert len(folders) == 1
        assert "lang" in folders[0].lower()

    def test_finds_lang_file(self, tmp_path: Path) -> None:
        """Finds en_US.lang file."""
        lang_dir = tmp_path / "mod1" / "assets" / "testmod" / "lang"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en_US.lang").write_text("key=value")

        folders = discover_lang_files(tmp_path, "en_US")
        assert len(folders) == 1

    def test_finds_multiple_mods(self, tmp_path: Path) -> None:
        """Finds language files across multiple mod directories."""
        for mod in ("mod_a", "mod_b"):
            lang_dir = tmp_path / mod / "assets" / "minecraft" / "lang"
            lang_dir.mkdir(parents=True)
            (lang_dir / "en_us.json").write_text('{"k": "v"}')

        folders = discover_lang_files(tmp_path, "en_us")
        assert len(folders) == 2

    def test_no_lang_files(self, tmp_path: Path) -> None:
        """Returns empty list when no language files found."""
        (tmp_path / "assets" / "textures").mkdir(parents=True)
        (tmp_path / "assets" / "textures" / "block.png").write_text("fake")

        folders = discover_lang_files(tmp_path, "en_us")
        assert folders == []

    def test_case_insensitive_matching(self, tmp_path: Path) -> None:
        """Language file matching is case-insensitive."""
        lang_dir = tmp_path / "mod1" / "assets" / "mod" / "lang"
        lang_dir.mkdir(parents=True)
        (lang_dir / "EN_US.JSON").write_text('{"k": "v"}')

        folders = discover_lang_files(tmp_path, "en_us")
        assert len(folders) == 1

    def test_handles_different_case_source_lang(self, tmp_path: Path) -> None:
        """Source language with different casing is handled."""
        lang_dir = tmp_path / "mod1" / "assets" / "mod" / "lang"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en_us.json").write_text('{"k": "v"}')

        folders = discover_lang_files(tmp_path, "EN_US")
        assert len(folders) == 1

    def test_lang_file_outside_lang_folder(self, tmp_path: Path) -> None:
        """Language files found outside standard 'lang' folder use parent folder."""
        assets_dir = tmp_path / "mod1" / "assets" / "mod"
        assets_dir.mkdir(parents=True)
        (assets_dir / "en_us.json").write_text('{"k": "v"}')

        folders = discover_lang_files(tmp_path, "en_us")
        # The parent folder (assets/mod) is used
        assert len(folders) == 1
        assert "mod" in folders[0]

    def test_deduplicates_folders(self, tmp_path: Path) -> None:
        """Multiple language files in the same folder produce one folder entry."""
        lang_dir = tmp_path / "mod1" / "assets" / "mod" / "lang"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en_us.json").write_text('{"k": "v"}')
        (lang_dir / "en_US.lang").write_text("k=v")

        folders = discover_lang_files(tmp_path, "en_us")
        assert len(folders) == 1


class TestDiscoverMcfunctionFolders:
    def test_finds_mcfunction_mods(self, tmp_path: Path) -> None:
        """Detects mod roots containing .mcfunction files."""
        mc_dir = tmp_path / "mod_datapack" / "data" / "mymod" / "functions"
        mc_dir.mkdir(parents=True)
        (mc_dir / "tick.mcfunction").write_text("say hello")

        folders = _discover_mcfunction_folders(tmp_path)
        assert len(folders) >= 1
        assert "mod_datapack" in str(folders[0])

    def test_no_mcfunction_files(self, tmp_path: Path) -> None:
        """Returns empty list when no .mcfunction files exist."""
        (tmp_path / "data" / "mod" / "functions").mkdir(parents=True)
        (tmp_path / "data" / "mod" / "functions" / "script.txt").write_text("hello")

        folders = _discover_mcfunction_folders(tmp_path)
        assert folders == []

    def test_multiple_mcfunction_mods(self, tmp_path: Path) -> None:
        """Finds multiple mods with .mcfunction files."""
        for mod in ("mod_a", "mod_b"):
            mc_dir = tmp_path / mod / "data" / "functions"
            mc_dir.mkdir(parents=True)
            (mc_dir / f"{mod}_tick.mcfunction").write_text("say hello")

        folders = _discover_mcfunction_folders(tmp_path)
        assert len(folders) == 2
