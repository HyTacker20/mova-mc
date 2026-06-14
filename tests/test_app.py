import contextlib

from app.interfaces.cli.args import build_argument_parser


class TestCommandLine:
    def test_parser_help(self):
        parser = build_argument_parser()
        with contextlib.suppress(SystemExit):
            parser.parse_args(["--help"])

    def test_parser_cli_command(self):
        parser = build_argument_parser()
        args = parser.parse_args(["cli", "-p", "./mods", "-s", "en_US", "-t", "uk_UA"])
        assert args.command == "cli"
        assert args.path == "./mods"
        assert args.source == "en_US"
        assert args.target == "uk_UA"

    def test_parser_tui_command(self):
        parser = build_argument_parser()
        args = parser.parse_args(["tui"])
        assert args.command == "tui"

    def test_parser_provider_flag(self):
        parser = build_argument_parser()
        args = parser.parse_args(["cli", "-s", "en_US", "--provider", "openai"])
        assert args.provider == "openai"
        assert args.source == "en_US"


class TestProgressReporter:
    def test_report_title(self):
        from app.utils.progress import ProgressReporter

        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))
        reporter.report_title("Test Title")
        assert len(events) == 1
        assert events[0][0] == "title"
        assert events[0][1]["text"] == "Test Title"

    def test_report_progress(self):
        from app.utils.progress import ProgressReporter

        events = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda event, **kwargs: events.append((event, kwargs)))
        reporter.report_progress(5, 10, "test")
        assert events[0][0] == "progress"
        assert events[0][1]["current"] == 5
        assert events[0][1]["total"] == 10

    def test_multiple_subscribers(self):
        from app.utils.progress import ProgressReporter

        results = []
        reporter = ProgressReporter()
        reporter.subscribe(lambda _event, **_kwargs: results.append(1))
        reporter.subscribe(lambda _event, **_kwargs: results.append(2))
        reporter.report_message("hi")
        assert results == [1, 2]
