import json
import zipfile
from pathlib import Path

from app.core.mod_scanner import ModScanner


class TestModScanner:
    def test_discover_mods_empty_dir(self, tmp_path: Path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        scanner = ModScanner(str(mods_dir))
        mods = scanner.discover_mods()
        assert mods == []

    def test_discover_mods_single_jar(self, tmp_path: Path, sample_en_us_json: dict):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()

        jar_path = mods_dir / "test_mod.jar"
        tmp_jar_dir = tmp_path / "_build"
        assets = tmp_jar_dir / "assets" / "testmod" / "lang"
        assets.mkdir(parents=True)
        (assets / "en_us.json").write_text(json.dumps(sample_en_us_json), encoding="utf-8")

        with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in __import__("os").walk(tmp_jar_dir):
                for f in files:
                    fp = Path(root) / f
                    zf.write(fp, str(fp.relative_to(tmp_jar_dir)))

        scanner = ModScanner(str(mods_dir))
        mods = scanner.discover_mods()
        assert len(mods) == 1
        assert mods[0].name == "test_mod.jar"
        assert mods[0].has_lang_files
        assert mods[0].estimated_entries == 4
        assert mods[0].selected is True

    def test_discover_mods_with_include_pattern(self, tmp_path: Path, sample_en_us_json: dict):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()

        for name in ("include_me.jar", "exclude_me.jar"):
            jar_path = mods_dir / name
            tmp_jar_dir = tmp_path / f"_build_{name}"
            assets = tmp_jar_dir / "assets" / "testmod" / "lang"
            assets.mkdir(parents=True)
            (assets / "en_us.json").write_text(json.dumps(sample_en_us_json), encoding="utf-8")

            with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in __import__("os").walk(tmp_jar_dir):
                    for f in files:
                        fp = Path(root) / f
                        zf.write(fp, str(fp.relative_to(tmp_jar_dir)))

        scanner = ModScanner(str(mods_dir))
        mods = scanner.discover_mods(include=["include_*"], exclude=[])
        selected = [m for m in mods if m.selected]
        assert len(selected) == 1
        assert selected[0].name == "include_me.jar"

    def test_discover_mods_with_exclude_pattern(self, tmp_path: Path, sample_en_us_json: dict):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()

        for name in ("keep.jar", "skip_this.jar"):
            jar_path = mods_dir / name
            tmp_jar_dir = tmp_path / f"_build_{name}"
            assets = tmp_jar_dir / "assets" / "testmod" / "lang"
            assets.mkdir(parents=True)
            (assets / "en_us.json").write_text(json.dumps(sample_en_us_json), encoding="utf-8")

            with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in __import__("os").walk(tmp_jar_dir):
                    for f in files:
                        fp = Path(root) / f
                        zf.write(fp, str(fp.relative_to(tmp_jar_dir)))

        scanner = ModScanner(str(mods_dir))
        mods = scanner.discover_mods(include=["*"], exclude=["skip_*"])
        selected = [m for m in mods if m.selected]
        skipped = [m for m in mods if not m.selected]
        assert len(selected) == 1
        assert selected[0].name == "keep.jar"
        assert len(skipped) == 1
        assert skipped[0].name == "skip_this.jar"

    def test_discover_mods_no_lang_files(self, tmp_path: Path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()

        jar_path = mods_dir / "no_lang.jar"
        tmp_jar_dir = tmp_path / "_build"
        meta = tmp_jar_dir / "META-INF"
        meta.mkdir(parents=True)
        (meta / "MANIFEST.MF").write_text("Manifest-Version: 1.0\n")

        with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in __import__("os").walk(tmp_jar_dir):
                for f in files:
                    fp = Path(root) / f
                    zf.write(fp, str(fp.relative_to(tmp_jar_dir)))

        scanner = ModScanner(str(mods_dir))
        mods = scanner.discover_mods()
        assert len(mods) == 1
        assert mods[0].has_lang_files is False
        assert mods[0].selected is False  # no lang files → not selected by default

    def test_discover_mods_with_lang_file(self, tmp_path: Path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()

        jar_path = mods_dir / "lang_mod.jar"
        tmp_jar_dir = tmp_path / "_build"
        assets = tmp_jar_dir / "assets" / "testmod" / "lang"
        assets.mkdir(parents=True)
        (assets / "en_US.lang").write_text("item.test=Test\nitem.other=Other\n", encoding="utf-8")

        with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in __import__("os").walk(tmp_jar_dir):
                for f in files:
                    fp = Path(root) / f
                    zf.write(fp, str(fp.relative_to(tmp_jar_dir)))

        scanner = ModScanner(str(mods_dir))
        mods = scanner.discover_mods()
        assert len(mods) == 1
        assert mods[0].estimated_entries == 2

    def test_discover_mods_with_mcfunction(self, tmp_path: Path):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()

        jar_path = mods_dir / "func_mod.jar"
        tmp_jar_dir = tmp_path / "_build"
        func_dir = tmp_jar_dir / "data" / "testmod" / "functions"
        func_dir.mkdir(parents=True)
        (func_dir / "test.mcfunction").write_text('say hello\ndata modify storage test:foo set value "bar"\n')

        with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in __import__("os").walk(tmp_jar_dir):
                for f in files:
                    fp = Path(root) / f
                    zf.write(fp, str(fp.relative_to(tmp_jar_dir)))

        scanner = ModScanner(str(mods_dir))
        mods = scanner.discover_mods()
        assert len(mods) == 1
        assert mods[0].mcfunction_count == 1
        assert mods[0].has_lang_files is True
        assert mods[0].selected is True

    def test_discover_mods_scan_progress_events(self, tmp_path: Path, sample_en_us_json: dict):
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()

        jar_path = mods_dir / "mod.jar"
        tmp_jar_dir = tmp_path / "_build"
        assets = tmp_jar_dir / "assets" / "testmod" / "lang"
        assets.mkdir(parents=True)
        (assets / "en_us.json").write_text(json.dumps(sample_en_us_json), encoding="utf-8")

        with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in __import__("os").walk(tmp_jar_dir):
                for f in files:
                    fp = Path(root) / f
                    zf.write(fp, str(fp.relative_to(tmp_jar_dir)))

        from app.utils.progress import ProgressReporter

        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **_kwargs: events.append(event))

        scanner = ModScanner(str(mods_dir), reporter=reporter)
        scanner.discover_mods()

        assert "scan_start" in events
        assert "scan_progress" in events
        assert "scan_complete" in events
