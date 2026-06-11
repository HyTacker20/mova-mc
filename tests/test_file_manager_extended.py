import json
import shutil
from pathlib import Path

from app.infrastructure.filesystem.jar_packager import _convert_folder_to_jar
from app.infrastructure.filesystem.lang_discovery import _discover_mcfunction_folders


class TestJarPackager:
    def test_convert_folder_to_jar(self, tmp_path: Path, sample_en_us_json: dict):
        folder_path = tmp_path / "mod_folder"
        assets = folder_path / "assets" / "testmod" / "lang"
        assets.mkdir(parents=True)
        en_path = assets / "en_us.json"
        en_path.write_text(json.dumps(sample_en_us_json), encoding="utf-8")
        jar_path = tmp_path / "output" / "test.jar"
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        _convert_folder_to_jar(folder_path, jar_path)
        assert jar_path.exists()
        assert jar_path.stat().st_size > 0

    def test_convert_translated_mods_multiple(self, tmp_path: Path, sample_en_us_json: dict):
        from app.infrastructure.filesystem.jar_packager import convert_translated_mods

        mods_dir = tmp_path / "mods"
        translation_dir = tmp_path / "translated"
        temp_dir = tmp_path / "temp"
        mods_dir.mkdir()
        translation_dir.mkdir()
        temp_dir.mkdir()

        for i in range(3):
            mod_folder = temp_dir / f"mod_{i}"
            assets = mod_folder / "assets" / "mod" / "lang"
            assets.mkdir(parents=True)
            en_path = assets / "en_us.json"
            en_path.write_text(json.dumps(sample_en_us_json), encoding="utf-8")
            uk_path = assets / "uk_ua.json"
            uk_path.write_text(json.dumps(sample_en_us_json), encoding="utf-8")

        convert_translated_mods(temp_dir, translation_dir, mods_dir, "uk_UA", "en_US")

        all_files = [f for f in translation_dir.iterdir() if f.is_file()]
        assert len(all_files) == 3

    def test_convert_translated_mods_same_paths(self, tmp_path: Path, sample_en_us_json: dict):
        from app.infrastructure.filesystem.jar_packager import convert_translated_mods

        shared_dir = tmp_path / "shared"
        temp_dir = tmp_path / "temp"
        shared_dir.mkdir()
        temp_dir.mkdir()

        mod_folder = temp_dir / "mod_0"
        assets = mod_folder / "assets" / "mod" / "lang"
        assets.mkdir(parents=True)
        (assets / "en_us.json").write_text(json.dumps(sample_en_us_json), encoding="utf-8")
        (assets / "uk_ua.json").write_text(json.dumps(sample_en_us_json), encoding="utf-8")

        convert_translated_mods(temp_dir, shared_dir, shared_dir, "uk_UA", "en_US")
        output = shared_dir / "mod_0"
        assert output.exists()


class TestLangDiscovery:
    def test_get_mcfunction_folders(self, tmp_path: Path):
        mc_dir = tmp_path / "mod.jar" / "data" / "test" / "functions"
        mc_dir.mkdir(parents=True)
        (mc_dir / "tick.mcfunction").write_text("say hello", encoding="utf-8")
        folders = _discover_mcfunction_folders(tmp_path)
        assert len(folders) >= 1


class TestWorkspaceCleanup:
    def test_remove_folder(self, tmp_path: Path):
        folder = tmp_path / "to_remove"
        folder.mkdir()
        (folder / "file.txt").write_text("test", encoding="utf-8")
        shutil.rmtree(str(folder), ignore_errors=True)
        assert not folder.exists()
