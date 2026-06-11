"""Polymorphic archive opener — ZIP or RAR, transparent to callers.

Uses ``rarfile`` for RAR archives (requires ``UnRAR.exe`` / ``unrar`` on PATH
or set via ``UNRAR_TOOL`` env var).  Raises :class:`RarBackendUnavailableError`
when the unrar backend is not available.
"""

from __future__ import annotations

import os
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

_RAR5_MAGIC = b"Rar!\x1a\x07\x01\x00"
_RAR4_MAGIC = b"Rar!\x1a\x07\x00"

_UNRAR_PATHS: tuple[str, ...] = (
    # Windows typical locations
    "C:\\Program Files\\WinRAR\\UnRAR.exe",
    "C:\\Program Files (x86)\\WinRAR\\UnRAR.exe",
)

_RAR_BACKEND_MSG = (
    "Install WinRAR / unrar and ensure UnRAR.exe is on PATH (or set UNRAR_TOOL)."
)


class ArchiveOpenError(Exception):
    """Base exception for archive open failures."""


class RarBackendUnavailableError(ArchiveOpenError):
    """RAR archive detected but ``unrar`` / ``UnRAR.exe`` backend is missing."""


def is_rar_archive(path: str | Path) -> bool:
    """Return True if *path* starts with a RAR magic byte sequence."""
    try:
        with Path(path).open("rb") as fh:
            header = fh.read(8)
        return header.startswith(_RAR5_MAGIC) or header.startswith(_RAR4_MAGIC)
    except OSError:
        return False


def _find_unrar() -> str | None:
    """Locate a working ``unrar`` / ``UnRAR.exe`` backend.

    Checks (in order):
    1. ``UNRAR_TOOL`` environment variable
    2. Standard Windows installation paths
    3. ``unrar`` on PATH (handled by ``rarfile`` itself)
    """
    env_tool = os.getenv("UNRAR_TOOL")
    if env_tool and Path(env_tool).is_file():
        return env_tool

    for candidate in _UNRAR_PATHS:
        if Path(candidate).is_file():
            return candidate

    return None


def _ensure_rar_backend() -> None:
    """Configure ``rarfile`` and verify the unrar backend is available."""
    try:
        import rarfile  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RarBackendUnavailableError(
            f"rarfile package is not installed. {_RAR_BACKEND_MSG}"
        ) from exc

    tool = _find_unrar()
    if tool:
        rarfile.UNRAR_TOOL = tool

    try:
        rarfile.tool_setup()
    except Exception as exc:
        raise RarBackendUnavailableError(
            f"Cannot find unrar/UnRAR.exe backend. {_RAR_BACKEND_MSG}"
        ) from exc


class _Archive(Protocol):
    """Subset of ``ZipFile`` / ``RarFile`` that callers depend on."""

    def namelist(self) -> list[str]: ...
    def read(self, name: str) -> bytes: ...
    def extractall(self, path: str | os.PathLike[str]) -> None: ...


@contextmanager
def open_archive(path: str | Path) -> Iterator[_Archive]:
    """Open *path* as a ZIP or RAR archive, auto-detecting the format.

    Yields a ``zipfile.ZipFile`` for ZIP / JAR files, or a ``rarfile.RarFile``
    for RAR archives.  Raises :class:`RarBackendUnavailableError` when the file
    is RAR but the unrar backend is missing.
    """
    path_str = str(path)

    if is_rar_archive(path_str):
        _ensure_rar_backend()
        import rarfile  # type: ignore[import-untyped]

        with rarfile.RarFile(path_str) as rf:
            yield rf  # type: ignore[return-value]
    else:
        with zipfile.ZipFile(path_str, "r") as zf:
            yield zf  # type: ignore[return-value]
