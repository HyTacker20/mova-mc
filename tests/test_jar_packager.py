"""Tests for jar_packager — convert_translated_mods mod_names filtering."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.filesystem.jar_packager import convert_translated_mods


def _populate_folder(base: Path, name: str) -> None:
    """Create a mod-like folder with a dummy file so the packager has something to pack."""
    folder = base / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "dummy.txt").write_text("test", encoding="utf-8")


def test_convert_selected_only(tmp_path: Path) -> None:
    """Only the mod whose name is in mod_names should produce a JAR."""
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    workspace.mkdir()
    output.mkdir()

    for name in ("A", "B", "C"):
        _populate_folder(workspace, name)

    packed = convert_translated_mods(
        temp_path=workspace,
        translation_path=output,
        mods_path=output,
        target_lang="es_ES",
        source_lang="en_US",
        mod_names=["B"],
    )

    assert packed == ["B"]
    assert (output / "B").exists(), "B should have been packed"
    assert not (output / "A").exists(), "A should NOT be packed"
    assert not (output / "C").exists(), "C should NOT be packed"


def test_convert_unknown_name_warns_and_skips(tmp_path: Path) -> None:
    """A mod_names entry with no matching workspace folder is skipped with a warning."""
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    workspace.mkdir()
    output.mkdir()

    _populate_folder(workspace, "RealMod")

    packed = convert_translated_mods(
        temp_path=workspace,
        translation_path=output,
        mods_path=output,
        target_lang="es_ES",
        source_lang="en_US",
        mod_names=["RealMod", "NoSuchMod"],
    )

    assert packed == ["RealMod"]
    assert (output / "RealMod").exists()
    assert not (output / "NoSuchMod").exists()


def test_convert_all_when_mod_names_none(tmp_path: Path) -> None:
    """When mod_names is None, pack every directory (backward compatibility)."""
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    workspace.mkdir()
    output.mkdir()

    for name in ("A", "B", "C"):
        _populate_folder(workspace, name)

    packed = convert_translated_mods(
        temp_path=workspace,
        translation_path=output,
        mods_path=output,
    )

    assert sorted(packed) == ["A", "B", "C"]
    for name in ("A", "B", "C"):
        assert (output / name).exists()
