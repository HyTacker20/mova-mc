import sys
from pathlib import Path

from loguru import logger

_logging_initialized = False


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
    global _logging_initialized
    if _logging_initialized:
        return

    logger.remove()
    log_file = Path(log_dir) / "translation.log"
    Path(log_dir).mkdir(parents=True, exist_ok=True)

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

    if console:
        # Level-first format matches uvicorn/stdlib (`INFO: …`) so IDE terminals
        # highlight log levels consistently alongside access-log lines.
        logger.add(
            sys.stderr,
            level=console_level,
            format="{level}: {time:HH:mm:ss} | {message}",
            colorize=True,
        )

    _logging_initialized = True


def is_logging_configured() -> bool:
    return _logging_initialized
