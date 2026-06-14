"""Tests for the resource pack builder."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.infrastructure.filesystem.resourcepack_builder import (
    _parse_mc_version,
    _version_to_pack_format,
    build_resource_pack,
    detect_pack_format,
    write_pack_mcmeta,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _make_workspace_file(workspace: Path, rel: str, content: str | None = None) -> Path:
    """Create a file at *workspace* / *rel* (parent dirs created automatically)."""
    fp = workspace / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content or "{}", encoding="utf-8")
    return fp


# ── write_pack_mcmeta ──────────────────────────────────────────────────


class TestPackMcmeta:
    def test_pack_mcmeta_is_valid(self, tmp_path: Path) -> None:
        """pack.mcmeta contains pack_format and description."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            write_pack_mcmeta(zf, pack_format=9)
        with zipfile.ZipFile(zip_path, "r") as zf:
            data = json.loads(zf.read("pack.mcmeta"))
        assert data["pack"]["pack_format"] == 9
        assert len(data["pack"]["description"]) > 0

    def test_pack_mcmeta_default_format(self, tmp_path: Path) -> None:
        """write_pack_mcmeta uses fallback when pack_format is None."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            write_pack_mcmeta(zf)
        with zipfile.ZipFile(zip_path, "r") as zf:
            data = json.loads(zf.read("pack.mcmeta"))
        assert data["pack"]["pack_format"] == 3  # fallback


# ── Version parsing ────────────────────────────────────────────────────


class TestParseMcVersion:
    def test_standard(self) -> None:
        assert _parse_mc_version("1.12.2") == (1, 12)

    def test_newer(self) -> None:
        assert _parse_mc_version("1.20.1") == (1, 20)

    def test_major_only(self) -> None:
        assert _parse_mc_version("1.8") == (1, 8)

    def test_invalid(self) -> None:
        assert _parse_mc_version("not a version") is None

    def test_version_to_pack_format_known(self) -> None:
        assert _version_to_pack_format((1, 12)) == 3
        assert _version_to_pack_format((1, 16)) == 6
        assert _version_to_pack_format((1, 20)) == 15

    def test_version_to_pack_format_unknown(self) -> None:
        assert _version_to_pack_format((1, 25)) == 3  # fallback


# ── detect_pack_format ─────────────────────────────────────────────────


class TestDetectPackFormat:
    def test_from_existing_mcmeta_is_ignored(self, tmp_path: Path) -> None:
        """Mod's pack.mcmeta is ignored — version from mcmod.info wins."""
        ws = tmp_path / "ws"
        ws.mkdir()
        _make_workspace_file(ws, "mod_a/pack.mcmeta", '{"pack":{"pack_format":1,"description":"mod"}}')
        _make_workspace_file(ws, "mod_a/mcmod.info",
            '[{"modid":"test","mcversion":"1.12.2"}]')

        # Should use mcmod.info → 1.12.2 → pack_format=3, NOT pack.mcmeta's 1
        assert detect_pack_format(ws) == 3

    def test_from_mcmod_info(self, tmp_path: Path) -> None:
        """Detect from Forge mcmod.info."""
        ws = tmp_path / "ws"
        ws.mkdir()
        _make_workspace_file(ws, "mod_a/mcmod.info",
            '[{"modid":"test","mcversion":"1.12.2"}]')

        assert detect_pack_format(ws) == 3

    def test_from_fabric_mod_json(self, tmp_path: Path) -> None:
        """Detect from fabric.mod.json."""
        ws = tmp_path / "ws"
        ws.mkdir()
        _make_workspace_file(ws, "mod_a/fabric.mod.json",
            '{"id":"test","depends":{"minecraft":"~1.19.2"}}')

        assert detect_pack_format(ws) == 9

    def test_from_mods_toml(self, tmp_path: Path) -> None:
        """Detect from META-INF/mods.toml."""
        ws = tmp_path / "ws"
        ws.mkdir()
        _make_workspace_file(ws, "mod_a/META-INF/mods.toml",
            'modLoader="javafml"\nversions="1.16.5"\n')

        assert detect_pack_format(ws) == 6

    def test_fallback_when_no_metadata(self, tmp_path: Path) -> None:
        """Fallback to 3 when no metadata found."""
        ws = tmp_path / "ws"
        ws.mkdir()
        _make_workspace_file(ws, "mod_a/assets/mymod/lang/en_us.json", "{}")

        assert detect_pack_format(ws) == 3

    def test_mcmod_info_wins_over_mcmeta(self, tmp_path: Path) -> None:
        """mcmod.info takes priority over pack.mcmeta for version detection."""
        ws = tmp_path / "ws"
        ws.mkdir()
        _make_workspace_file(ws, "mod_a/pack.mcmeta", '{"pack":{"pack_format":15}}')
        _make_workspace_file(ws, "mod_a/mcmod.info",
            '[{"modid":"test","mcversion":"1.12.2"}]')

        assert detect_pack_format(ws) == 3  # mcmod.info wins


# ── build_resource_pack ────────────────────────────────────────────────


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
        _make_workspace_file(ws, "mod_a/README.txt", "hello")

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test", pack_format=3)

        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = sorted(zf.namelist())
        assert "pack.mcmeta" in names
        assert "assets/mymod/lang/uk_ua.json" in names
        assert "assets/mymod/lang/en_us.json" not in names
        assert "assets/mymod/lang/es_es.json" not in names

    def test_directory_structure_preservation(self, tmp_path: Path) -> None:
        """Translated files preserve ``assets/<ns>/lang/`` inside the zip."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_a/assets/testmod/lang/uk_ua.json", '{"apple":"Яблуко"}')
        _make_workspace_file(ws, "mod_b/assets/other/lang/uk_ua.lang", "key=value\n")

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test", pack_format=3)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = sorted(zf.namelist())
        assert "assets/testmod/lang/uk_ua.json" in names
        assert "assets/other/lang/uk_ua.lang" in names

    def test_lang_file_support(self, tmp_path: Path) -> None:
        """``.lang`` files matching target lang are included."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_c/assets/mod/lang/uk_UA.lang", "item.diamond.name=Діамант\n")

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test", pack_format=3)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = sorted(zf.namelist())
            assert "assets/mod/lang/uk_UA.lang" in names
            content = zf.read("assets/mod/lang/uk_UA.lang").decode("utf-8")
        assert "Діамант" in content

    def test_empty_workspace(self, tmp_path: Path) -> None:
        """Empty workspace produces a zip with only pack.mcmeta."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test", pack_format=3)

        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert names == ["pack.mcmeta", "pack.png"]

    def test_no_matching_files(self, tmp_path: Path) -> None:
        """Workspace with files but none matching target_lang still yields pack.mcmeta."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_a/assets/mymod/lang/en_us.json", '{"stone":"Stone"}')
        _make_workspace_file(ws, "mod_a/assets/mymod/lang/es_es.json", '{"stone":"Piedra"}')

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test", pack_format=3)

        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert names == ["pack.mcmeta", "pack.png"]

    def test_auto_detect_pack_format(self, tmp_path: Path) -> None:
        """When pack_format is not provided, it's auto-detected from metadata."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        # Simulate a 1.16.5 mod
        _make_workspace_file(ws, "mod_a/assets/mymod/lang/uk_ua.json", '{"stone":"Камінь"}')
        _make_workspace_file(ws, "mod_a/mcmod.info",
            '[{"modid":"test","mcversion":"1.16.5"}]')

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test")
        # pack_format should be auto-detected as 6 (for 1.16)

        with zipfile.ZipFile(zip_path, "r") as zf:
            data = json.loads(zf.read("pack.mcmeta"))
        assert data["pack"]["pack_format"] == 6

    def test_mcmod_info_wins_over_mcmeta_in_build(self, tmp_path: Path) -> None:
        """mcmod.info version detection wins over mod's pack.mcmeta during build."""
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()

        _make_workspace_file(ws, "mod_a/assets/mymod/lang/uk_ua.json", '{"stone":"Камінь"}')
        _make_workspace_file(ws, "mod_a/pack.mcmeta", '{"pack":{"pack_format":12,"description":"mod"}}')
        _make_workspace_file(ws, "mod_a/mcmod.info",
            '[{"modid":"test","mcversion":"1.12.2"}]')

        zip_path = build_resource_pack(ws, out, "uk_UA", "mova_test")

        with zipfile.ZipFile(zip_path, "r") as zf:
            data = json.loads(zf.read("pack.mcmeta"))
        assert data["pack"]["pack_format"] == 3  # mcmod.info wins over pack.mcmeta
