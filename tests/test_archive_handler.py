from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.filesystem.archive_handler import (
    RarBackendUnavailableError,
    is_rar_archive,
    open_archive,
)

_RAR4_HEADER = b"Rar!\x1a\x07\x00"


class TestIsRarArchive:
    def test_detects_rar4_magic(self, tmp_path: Path):
        rar_path = tmp_path / "fake.jar"
        rar_path.write_bytes(_RAR4_HEADER + b"\x00" * 100)
        assert is_rar_archive(rar_path) is True

    def test_zip_is_not_rar(self, tmp_path: Path):
        jar_path = tmp_path / "mod.jar"
        with zipfile.ZipFile(jar_path, "w") as zf:
            zf.writestr("test.txt", "hello")
        assert is_rar_archive(jar_path) is False


class TestOpenArchiveZip:
    def test_opens_zip_jar(self, tmp_path: Path):
        jar_path = tmp_path / "mod.jar"
        with zipfile.ZipFile(jar_path, "w") as zf:
            zf.writestr("assets/mod/lang/en_us.json", '{"key": "value"}')

        with open_archive(jar_path) as archive:
            names = archive.namelist()
            assert "assets/mod/lang/en_us.json" in names
            assert archive.read("assets/mod/lang/en_us.json") == b'{"key": "value"}'


class TestOpenArchiveRar:
    def test_rar_without_backend_raises(self, tmp_path: Path):
        rar_path = tmp_path / "mod.jar"
        rar_path.write_bytes(_RAR4_HEADER + b"\x00" * 100)

        with (
            patch(
                "app.infrastructure.filesystem.archive_handler._ensure_rar_backend",
                side_effect=RarBackendUnavailableError("no backend"),
            ),
            pytest.raises(RarBackendUnavailableError, match="no backend"),
            open_archive(rar_path),
        ):
            pass

    def test_rar_with_backend_yields_archive(self, tmp_path: Path):
        rar_path = tmp_path / "mod.jar"
        rar_path.write_bytes(_RAR4_HEADER + b"\x00" * 100)

        mock_rar = MagicMock()
        mock_rar.namelist.return_value = ["file.txt"]
        mock_rar.__enter__ = MagicMock(return_value=mock_rar)
        mock_rar.__exit__ = MagicMock(return_value=False)

        mock_rarfile = MagicMock()
        mock_rarfile.RarFile.return_value = mock_rar

        with (
            patch(
                "app.infrastructure.filesystem.archive_handler._ensure_rar_backend",
            ),
            patch.dict("sys.modules", {"rarfile": mock_rarfile}),
            open_archive(rar_path) as archive,
        ):
            assert archive.namelist() == ["file.txt"]

        mock_rarfile.RarFile.assert_called_once_with(str(rar_path))
