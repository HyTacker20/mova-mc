import sys
from collections.abc import Callable
from pathlib import Path

from loguru import logger

_logging_initialized = False
_log_file_path: str = ""
_console_handler_id: int | None = None


def setup_logging(
    log_dir: str = "logs",
    console_level: str = "INFO",
    *,
    json_format: bool = False,
    console: bool = True,
) -> None:
    """Configure loguru logging.

    Args:
        log_dir: Directory for the rotating log file.
        console_level: Minimum log level for the stderr sink.
        json_format: Serialize log file as JSON.
        console: When False, skip the stderr sink entirely (for TUI use).
            The rotating file sink is always registered so full details
            are captured to disk.
    """
    global _logging_initialized, _console_handler_id, _log_file_path
    if _logging_initialized:
        return

    logger.remove()
    log_file = Path(log_dir) / "translation.log"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    _log_file_path = str(log_file.resolve())

    if json_format:
        logger.add(
            str(log_file),
            rotation="5 MB",
            retention=3,
            level="DEBUG",
            serialize=True,
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
        )
    else:
        logger.add(
            str(log_file),
            rotation="5 MB",
            retention=3,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
        )

    _console_handler_id = None
    if console:
        _console_handler_id = logger.add(
            sys.stderr,
            level=console_level,
            format="{time:HH:mm:ss} | {level: <8} | {message}",
            colorize=True,
        )

    _logging_initialized = True


def setup_logging_for_tui(log_dir: str = "logs") -> None:
    """Configure logging for the Textual TUI — file only, no stderr sink.

    Full backtrace/diagnose detail is written to the log file so the UI
    never sees raw tracebacks or noisy stderr output.
    """
    setup_logging(log_dir=log_dir, console=False)


def is_logging_configured() -> bool:
    return _logging_initialized


def get_console_handler_id() -> int | None:
    return _console_handler_id


def get_log_file_path() -> str:
    """Return the absolute path to the rotating log file."""
    return _log_file_path


def get_logger():
    return logger


def add_callback_sink(
    callback: Callable[[str], None],
    level: str = "INFO",
) -> int:
    """Register a loguru sink that invokes *callback* for each log line.

    Returns the sink ID for later removal via ``logger.remove(id)``.
    """
    return logger.add(callback, level=level, format="{message}")
