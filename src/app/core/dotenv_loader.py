"""Load .env files from the project root and CWD."""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_dotenv_files() -> None:
    """Load environment variables from CWD and the project-root .env file."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv()
    project_env = _PROJECT_ROOT / ".env"
    if project_env.is_file():
        load_dotenv(dotenv_path=str(project_env))
