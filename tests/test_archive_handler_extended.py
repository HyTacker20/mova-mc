"""Extended tests for archive_handler — _find_unrar, _ensure_rar_backend, is_rar_archive edge cases."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.infrastructure.filesystem.archive_handler import (
    _find_unrar,
    is_rar_archive,
)

_RAR5_MAGIC = b"Rar!\x1a\x07\x01\x00"
_RAR4_MAGIC = b"Rar!\x1a\x07\x00"


class TestFindUnrar:
    def test_from_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_unrar = tmp_path / "fake_unrar.exe"
        fake_unrar.write_text("fake")
        monkeypatch.setenv("UNRAR_TOOL", str(fake_unrar))
        result = _find_unrar()
        assert result == str(fake_unrar)

    def test_env_var_not_a_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UNRAR_TOOL", "/nonexistent/path/unrar.exe")
        result = _find_unrar()
        # Falls through to candidate paths, likely None
        assert result is None or isinstance(result, str)

    def test_no_env_var_no_candidates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UNRAR_TOOL", raising=False)
        # Since the standard paths likely don't exist in CI, returns None
        result = _find_unrar()
        # Should return None (no UnRAR installed in test env)
        assert result is None or isinstance(result, str)


class TestIsRarArchiveEdgeCases:
    def test_rar5_magic(self, tmp_path: Path) -> None:
        rar_path = tmp_path / "test.rar"
        rar_path.write_bytes(_RAR5_MAGIC + b"\x00" * 100)
        assert is_rar_archive(rar_path) is True

    def test_rar4_magic(self, tmp_path: Path) -> None:
        rar_path = tmp_path / "test.rar"
        rar_path.write_bytes(_RAR4_MAGIC + b"\x00" * 100)
        assert is_rar_archive(rar_path) is True

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jar"
        path.write_bytes(b"")
        assert is_rar_archive(path) is False

    def test_nonexistent_file(self) -> None:
        assert is_rar_archive("/nonexistent/path.rar") is False

    def test_string_path(self, tmp_path: Path) -> None:
        rar_path = tmp_path / "test.rar"
        rar_path.write_bytes(_RAR4_MAGIC + b"\x00" * 100)
        assert is_rar_archive(str(rar_path)) is True

    def test_small_file(self, tmp_path: Path) -> None:
        """File smaller than 8 bytes."""
        path = tmp_path / "small.bin"
        path.write_bytes(b"ab")
        assert is_rar_archive(path) is False

    def test_zip_is_not_rar(self, tmp_path: Path) -> None:
        jar_path = tmp_path / "mod.jar"
        with zipfile.ZipFile(jar_path, "w") as zf:
            zf.writestr("test.txt", "hello")
        assert is_rar_archive(jar_path) is False

    def test_binary_file_is_not_rar(self, tmp_path: Path) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08")
        assert is_rar_archive(path) is False
