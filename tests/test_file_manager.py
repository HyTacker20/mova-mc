import json
from pathlib import Path

from app.infrastructure.filesystem.jar_unpacker import unpack_mods
from app.infrastructure.filesystem.lang_discovery import discover_lang_files
from app.infrastructure.parsers import lang_parser, mcfunction_parser
from app.infrastructure.parsers.json_parser import parse_json_with_comments


class TestJsonParsing:
    def test_read_json_file(self, clean_sample_en_us_json_path: Path):
        data = parse_json_with_comments(clean_sample_en_us_json_path)
        assert data["item.minecraft.diamond"] == "Diamond"
        assert len(data) == 4

    def test_write_json_file(self, tmp_path: Path, sample_en_us_json: dict):
        out_path = tmp_path / "sub" / "output.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(sample_en_us_json, f, indent=4)
        assert out_path.exists()
        with out_path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert data == sample_en_us_json


class TestLangParsing:
    def test_read_lang_file(self, sample_en_us_lang_file: Path):
        data = lang_parser.read_lang_file(sample_en_us_lang_file)
        assert data["item.diamond.name"] == "Diamond"
        assert data["item.gold_ingot.name"] == "Gold Ingot"
        assert len(data) == 4

    def test_write_lang_file(self, tmp_path: Path, sample_en_us_json: dict):
        out_path = tmp_path / "output.lang"
        lang_parser.write_lang_file(sample_en_us_json, out_path)
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        for key, value in sample_en_us_json.items():
            assert f"{key}={value}" in content


class TestMcfunctionParsing:
    def test_read_mcfunction_file(self, sample_mcfunction_file: Path):
        data = mcfunction_parser.read_mcfunction_file(sample_mcfunction_file)
        assert len(data) == 3
        values = list(data.values())
        assert "Player joined the game" in values
        assert "Welcome to the arena!" in values
        assert "Goodbye, see you next time!" in values

    def test_write_mcfunction_file(self, sample_mcfunction_file: Path):
        data = mcfunction_parser.read_mcfunction_file(sample_mcfunction_file)
        translated = {key: "TR_" + val for key, val in data.items()}
        mcfunction_parser.write_mcfunction_file(sample_mcfunction_file, translated)
        data_after = mcfunction_parser.read_mcfunction_file(sample_mcfunction_file)
        for v in data_after.values():
            assert v.startswith("TR_")


class TestJarUnpacking:
    def test_unpack_mods(self, temp_mods_dir: Path, sample_jar: Path, tmp_path: Path):
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        unpack_mods(Path(temp_mods_dir), temp_dir)
        unpacked = temp_dir / "test_mod.jar"
        assert unpacked.exists()
        lang_dir = unpacked / "assets" / "testmod" / "lang"
        assert lang_dir.exists()


class TestLangDiscovery:
    def test_discover_lang_files(self, temp_mods_dir: Path, sample_jar: Path, tmp_path: Path):
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        unpack_mods(Path(temp_mods_dir), temp_dir)
        folders = discover_lang_files(temp_dir, "en_US")
        assert len(folders) > 0
