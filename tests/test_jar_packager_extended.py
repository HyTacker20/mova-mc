"""Extended tests for jar_packager — _update_pack_mcmeta, _convert_folder_to_jar edge cases."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.infrastructure.filesystem.jar_packager import (
    _convert_folder_to_jar,
    _update_pack_mcmeta,
    convert_translated_mods,
)


class TestUpdatePackMcmeta:
    def test_adds_language_to_mcmeta(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        folder.mkdir()
        mcmeta = folder / "pack.mcmeta"
        mcmeta.write_text(json.dumps({
            "pack": {"pack_format": 15, "description": "Test"},
            "language": {},
        }))

        _update_pack_mcmeta(folder, "uk_UA")

        data = json.loads(mcmeta.read_text())
        assert "uk_UA" in data["language"]
        assert "name" in data["language"]["uk_UA"]
        assert "region" in data["language"]["uk_UA"]
        assert data["language"]["uk_UA"]["region"] == "UA"

    def test_no_language_key_skips(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        folder.mkdir()
        mcmeta = folder / "pack.mcmeta"
        mcmeta.write_text(json.dumps({"pack": {"pack_format": 15}}))

        _update_pack_mcmeta(folder, "uk_UA")
        data = json.loads(mcmeta.read_text())
        assert "language" not in data

    def test_no_mcmeta_file(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        folder.mkdir()
        # No pack.mcmeta file — should not raise
        _update_pack_mcmeta(folder, "uk_UA")

    def test_lang_without_region(self, tmp_path: Path) -> None:
        """Language without underscore (no region)."""
        folder = tmp_path / "mod"
        folder.mkdir()
        mcmeta = folder / "pack.mcmeta"
        mcmeta.write_text(json.dumps({"language": {}}))

        _update_pack_mcmeta(folder, "en")
        data = json.loads(mcmeta.read_text())
        assert "en" in data["language"]
        assert data["language"]["en"]["region"] == ""

    def test_invalid_json_no_crash(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        folder.mkdir()
        mcmeta = folder / "pack.mcmeta"
        mcmeta.write_text("not valid json {{{")

        # Should not raise
        _update_pack_mcmeta(folder, "uk_UA")


class TestConvertFolderToJar:
    def test_creates_jar_with_lang_files(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        assets = folder / "assets" / "mod" / "lang"
        assets.mkdir(parents=True)
        (assets / "en_us.json").write_text('{"key": "value"}')
        (assets / "uk_ua.json").write_text('{"key": "значення"}')

        jar_path = tmp_path / "output" / "mod.jar"
        _convert_folder_to_jar(folder, jar_path, target_lang="uk_UA")

        assert jar_path.exists()
        with zipfile.ZipFile(jar_path, "r") as zf:
            names = zf.namelist()
            assert any("uk_ua.json" in n for n in names)

    def test_no_lang_files_warning(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        folder.mkdir()
        (folder / "data.txt").write_text("hello")

        jar_path = tmp_path / "output" / "mod.jar"
        _convert_folder_to_jar(folder, jar_path, target_lang="uk_UA")

        # JAR should still be created even without lang files
        assert jar_path.exists()

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        folder.mkdir()
        (folder / "data.txt").write_text("hello")

        jar_path = tmp_path / "deeply" / "nested" / "output" / "mod.jar"
        _convert_folder_to_jar(folder, jar_path)

        assert jar_path.exists()
        assert jar_path.parent.exists()

    def test_with_pack_mcmeta(self, tmp_path: Path) -> None:
        folder = tmp_path / "mod"
        folder.mkdir()
        mcmeta = folder / "pack.mcmeta"
        mcmeta.write_text(json.dumps({"language": {}}))
        (folder / "assets" / "mod" / "lang").mkdir(parents=True)
        (folder / "assets" / "mod" / "lang" / "uk_ua.json").write_text('{"k": "v"}')

        jar_path = tmp_path / "mod.jar"
        _convert_folder_to_jar(folder, jar_path, target_lang="uk_UA")

        assert jar_path.exists()
        with zipfile.ZipFile(jar_path, "r") as zf:
            names = zf.namelist()
            # pack.mcmeta should be in the JAR
            assert any("pack.mcmeta" in n for n in names)


class TestConvertTranslatedMods:
    def test_same_paths_warning(self, tmp_path: Path) -> None:
        """When mods_path == translation_path, a warning is logged."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()

        # Create a mod folder with a file
        mod_folder = workspace / "TestMod"
        mod_folder.mkdir()
        (mod_folder / "dummy.txt").write_text("test")

        packed = convert_translated_mods(
            temp_path=workspace,
            translation_path=output,
            mods_path=output,  # same path
            target_lang="es_ES",
            source_lang="en_US",
        )
        assert "TestMod" in packed
