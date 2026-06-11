from pathlib import Path

from loguru import logger

from app.logging_config import get_logger, setup_logging


class TestLoggingConfig:
    def test_setup_logging_creates_file_handler(self, tmp_path: Path):
        log_dir = tmp_path / "app_logs"
        setup_logging(log_dir=str(log_dir), console_level="WARNING")
        log_file = log_dir / "translation.log"
        assert log_dir.exists()
        log_file.write_text("test", encoding="utf-8")
        assert log_file.exists()

    def test_get_logger_returns_loguru_logger(self):
        lg = get_logger()
        assert lg is logger

    def test_setup_logging_clears_previous_handlers(self, tmp_path: Path):
        log_dir = str(tmp_path / "logs_clear")
        setup_logging(log_dir=log_dir, console_level="INFO")
        initial_count = len(logger._core.handlers)
        setup_logging(log_dir=log_dir, console_level="ERROR")
        assert len(logger._core.handlers) == initial_count
