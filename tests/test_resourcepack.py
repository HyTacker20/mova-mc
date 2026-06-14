"""Tests for the resource pack builder."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.infrastructure.filesystem.resourcepack_builder import (
    build_resource_pack,
    write_pack_mcmeta,
)

# ── write_pack_mcmeta ──────────────────────────────────────────────────


class TestPackMcmeta:
    def test_pack_mcmeta_is_valid(self, tmp_path: Path) -> None:
        """pack.mcmeta contains pack_format and description."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            write_pack_mcmeta(zf)
        with zipfile.ZipFile(zip_path, "r") as zf:
            data = json.loads(zf.read("pack.mcmeta"))
        assert data["pack"]["pack_format"] == 15
        assert len(data["pack"]["description"]) > 0


# ── build_resource_pack ────────────────────────────────────────────────


def _make_workspace_file(workspace: Path, rel: str, content: str | None = None) -> Path:
    """Create a file at *workspace* / *rel* (parent dirs created automatically)."""
    fp = workspace / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content or "{}", encoding="utf-8")
    return fp


class TestBuildResourcePack:
    def test_target_lang_only_filtering(self, tmp_path: Path) -> None:
        """Only files matching *target_lang* are included; other files are ignored."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_a/assets/mymod/lang/uk_ua.json", '{"stone":"Камінь"}')
        _make_workspace_file(ws, "mod_a/assets/mymod/lang/en_us.json", '{"stone":"Stone"}')
        _make_workspace_file(ws, "mod_a/assets/mymod/lang/es_es.json", '{"stone":"Piedra"}')
        # a random non-lang file
        _make_workspace_file(ws, "mod_a/README.txt", "hello")

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test")

        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = sorted(zf.namelist())
        # Only pack.mcmeta + uk_ua.json
        assert "pack.mcmeta" in names
        assert "mod_a/assets/mymod/lang/uk_ua.json" in names
        assert "mod_a/assets/mymod/lang/en_us.json" not in names
        assert "mod_a/assets/mymod/lang/es_es.json" not in names

    def test_directory_structure_preservation(self, tmp_path: Path) -> None:
        """Translated files preserve ``assets/<ns>/lang/`` inside the zip."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_a/assets/testmod/lang/uk_ua.json", '{"apple":"Яблуко"}')
        _make_workspace_file(ws, "mod_b/assets/other/lang/uk_ua.lang", "key=value\n")

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test")

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = sorted(zf.namelist())
        assert "mod_a/assets/testmod/lang/uk_ua.json" in names
        assert "mod_b/assets/other/lang/uk_ua.lang" in names

    def test_lang_file_support(self, tmp_path: Path) -> None:
        """``.lang`` files matching target lang are included."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_c/assets/mod/lang/uk_UA.lang", "item.diamond.name=Діамант\n")

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test")

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = sorted(zf.namelist())
            assert "mod_c/assets/mod/lang/uk_UA.lang" in names
            content = zf.read("mod_c/assets/mod/lang/uk_UA.lang").decode("utf-8")
        assert "Діамант" in content

    def test_empty_workspace(self, tmp_path: Path) -> None:
        """Empty workspace produces a zip with only pack.mcmeta."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test")

        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert names == ["pack.mcmeta"]

    def test_no_matching_files(self, tmp_path: Path) -> None:
        """Workspace with files but none matching target_lang still yields pack.mcmeta."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_a/assets/mymod/lang/en_us.json", '{"stone":"Stone"}')
        _make_workspace_file(ws, "mod_a/assets/mymod/lang/es_es.json", '{"stone":"Piedra"}')

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test")

        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert names == ["pack.mcmeta"]
