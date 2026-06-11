import sys
from unittest.mock import patch

import pytest

from app.interfaces.cli.args import build_argument_parser
from app.interfaces.cli.main import main


class TestCommandLineExtended:
    def test_main_no_args_shows_help(self):
        with patch("sys.argv", ["mova"]), patch.object(sys.stdout, "write") as mock_write:
            main()
            mock_write.assert_called()

    def test_main_app_command(self):
        with (
            patch("sys.argv", ["mova", "app"]),
            patch("app.interfaces.tui.main.main") as mock_tui_main,
        ):
            main()
            mock_tui_main.assert_called_once()

    def test_main_cli_subcommand(self):
        with (
            patch("sys.argv", ["mova", "cli", "-s", "en_US", "-t", "uk_UA"]),
            patch("app.interfaces.cli.main._run_translation") as mock_run,
        ):
            main()
            mock_run.assert_called_once()

    def test_main_error_handling(self):
        with (
            patch("sys.argv", ["mova", "cli", "-s", "en_US"]),
            patch("app.interfaces.cli.main._run_translation", side_effect=Exception("test error")),
            patch("app.interfaces.cli.main.logger") as mock_logger,
        ):
            with pytest.raises(SystemExit):
                main()
            mock_logger.exception.assert_called_once()

    def test_backward_compatibility(self):
        with (
            patch("sys.argv", ["mova", "cli", "-s", "en_US", "-t", "uk_UA"]),
            patch("app.interfaces.cli.main._run_translation") as mock_run,
        ):
            main()
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args.source == "en_US"
            assert call_args.target == "uk_UA"

    def test_parser_subparsers_exist(self):
        parser = build_argument_parser()
        with patch("sys.argv", ["mova", "cli", "-s", "en_US"]):
            args = parser.parse_args(["cli", "-s", "en_US"])
            assert args.command == "cli"
