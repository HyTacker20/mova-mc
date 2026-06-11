from app.utils.progress import ProgressReporter


class TestProgressExtended:
    def test_report_complete(self):
        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))
        reporter.report_complete("/output/path")
        assert len(events) == 1
        assert events[0][0] == "complete"
        assert events[0][1]["output_path"] == "/output/path"

    def test_report_error(self):
        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))
        reporter.report_error("Something went wrong")
        assert len(events) == 1
        assert events[0][0] == "error"
        assert events[0][1]["text"] == "Something went wrong"

    def test_report_scan_events(self):
        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))

        reporter.report_scan_start(10)
        assert events[-1][0] == "scan_start"
        assert events[-1][1]["total"] == 10

        reporter.report_scan_progress(5, 10, "mod.jar")
        assert events[-1][0] == "scan_progress"
        assert events[-1][1]["current"] == 5
        assert events[-1][1]["name"] == "mod.jar"

        reporter.report_scan_complete(10)
        assert events[-1][0] == "scan_complete"
        assert events[-1][1]["total"] == 10

    def test_report_mod_events(self):
        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))

        reporter.report_mod_start("test_mod", file_count=3, entry_count=100)
        assert events[-1][0] == "mod_start"
        assert events[-1][1]["mod_name"] == "test_mod"
        assert events[-1][1]["file_count"] == 3
        assert events[-1][1]["entry_count"] == 100

        reporter.report_mod_file_start("test_mod", "en_us.json", 50)
        assert events[-1][0] == "mod_file_start"
        assert events[-1][1]["file_path"] == "en_us.json"

        reporter.report_mod_file_progress("test_mod", "en_us.json", 25, 50)
        assert events[-1][0] == "mod_file_progress"
        assert events[-1][1]["current"] == 25

        reporter.report_mod_file_complete("test_mod", "en_us.json", 1200, 0)
        assert events[-1][0] == "mod_file_complete"
        assert events[-1][1]["duration_ms"] == 1200

        reporter.report_mod_complete("test_mod", 100, 100, 0)
        assert events[-1][0] == "mod_complete"
        assert events[-1][1]["translated"] == 100

    def test_report_overall_progress(self):
        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))

        reporter.report_overall_progress(3, 5, 450, 1200)
        assert events[-1][0] == "overall_progress"
        assert events[-1][1]["completed_mods"] == 3
        assert events[-1][1]["total_mods"] == 5
        assert events[-1][1]["completed_entries"] == 450
        assert events[-1][1]["total_entries"] == 1200

    def test_overall_progress_failed_entries(self):
        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))

        reporter.report(
            "overall_progress",
            completed_mods=1,
            total_mods=3,
            completed_entries=50,
            total_entries=200,
            failed_entries=2,
            fractional_mods=1.25,
        )
        payload = events[-1][1]
        assert payload["failed_entries"] == 2
        assert payload["fractional_mods"] == 1.25

    def test_report_repack_events(self):
        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))

        reporter.report_repack_start(5)
        assert events[-1][0] == "repack_start"

        reporter.report_repack_progress(2, 5, "mod.jar")
        assert events[-1][0] == "repack_progress"
        assert events[-1][1]["current"] == 2
        assert events[-1][1]["name"] == "mod.jar"

        reporter.report_repack_complete(5)
        assert events[-1][0] == "repack_complete"
