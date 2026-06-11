import time

from app.domain.stats import FileStats, ModStats, OverallStats


class TestFileStats:
    def test_init_defaults(self):
        fs = FileStats(path="test.json", file_type="json")
        assert fs.path == "test.json"
        assert fs.file_type == "json"
        assert fs.entries_total == 0
        assert fs.entries_translated == 0
        assert fs.entries_failed == 0
        assert fs.duration_ms == 0

    def test_start_finish_timing(self):
        fs = FileStats(path="test.json", file_type="json")
        fs.start()
        time.sleep(0.02)
        fs.finish()
        assert fs.duration_ms >= 10

    def test_add_translated(self):
        fs = FileStats(path="test.json", file_type="json")
        fs.add_translated(10)
        fs.add_translated(5)
        assert fs.entries_translated == 15

    def test_add_failed(self):
        fs = FileStats(path="test.json", file_type="json")
        fs.add_failed(3)
        assert fs.entries_failed == 3


class TestModStats:
    def test_init_defaults(self):
        ms = ModStats(name="test_mod")
        assert ms.name == "test_mod"
        assert ms.files == []
        assert ms.skipped is False

    def test_start_finish_aggregates(self):
        ms = ModStats(name="test_mod")
        ms.start()
        time.sleep(0.02)

        fs1 = FileStats(path="a.json", file_type="json")
        fs1.entries_total = 10
        fs1.add_translated(10)
        ms.files.append(fs1)

        fs2 = FileStats(path="b.json", file_type="json")
        fs2.entries_total = 5
        fs2.add_translated(3)
        fs2.add_failed(2)
        ms.files.append(fs2)

        ms.finish()
        assert ms.total_entries == 15
        assert ms.translated_entries == 13
        assert ms.failed_entries == 2
        assert ms.duration_ms >= 15

    def test_skipped_flag(self):
        ms = ModStats(name="skipped_mod", skipped=True)
        ms.finish()
        assert ms.skipped is True
        assert ms.total_entries == 0


class TestOverallStats:
    def test_init_defaults(self):
        os = OverallStats()
        assert os.mods == []
        assert os.provider == ""
        assert os.source_lang == ""

    def test_start_finish_aggregates(self):
        os = OverallStats()
        os.provider = "google"
        os.source_lang = "en"
        os.target_lang = "uk"
        os.start()
        time.sleep(0.02)

        ms1 = ModStats(name="mod1")
        ms1.total_entries = 10
        ms1.translated_entries = 10
        os.mods.append(ms1)

        ms2 = ModStats(name="mod2", skipped=True)
        ms2.total_entries = 5
        os.mods.append(ms2)

        os.finish()
        assert os.total_mods == 2
        assert os.translated_mods == 1
        assert os.skipped_mods == 1
        assert os.total_entries == 15
        assert os.translated_entries == 10
        assert os.total_duration_ms >= 15

    def test_to_dict(self):
        os = OverallStats()
        os.provider = "openai"
        os.source_lang = "en_US"
        os.target_lang = "uk_UA"
        os.total_mods = 2
        os.translated_mods = 2
        os.total_entries = 100
        os.translated_entries = 100

        ms = ModStats(name="mod1")
        ms.total_entries = 50
        ms.translated_entries = 50
        ms.duration_ms = 1000

        fs = FileStats(path="en_us.json", file_type="json")
        fs.entries_total = 50
        fs.entries_translated = 50
        fs.duration_ms = 800
        ms.files.append(fs)

        os.mods.append(ms)

        result = os.to_dict()
        assert result["total_mods"] == 2
        assert result["provider"] == "openai"
        assert result["source_lang"] == "en_US"
        assert result["target_lang"] == "uk_UA"
        assert len(result["mods"]) == 1
        assert result["mods"][0]["name"] == "mod1"
        assert result["mods"][0]["total_entries"] == 50
        assert len(result["mods"][0]["files"]) == 1
        assert result["mods"][0]["files"][0]["path"] == "en_us.json"
