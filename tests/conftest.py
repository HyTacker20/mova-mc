import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clear_cancel_token() -> None:
    """Ensure the global cancel token is cleared before every test.

    Some tests set the token but
    don't restore it, which leaks into subsequent tests that call
    ``cancel_token.raise_if_set()``.
    """
    from app.utils.cancellation import cancel_token

    cancel_token.clear()


@pytest.fixture
def sample_en_us_json() -> dict:
    return {
        "item.minecraft.diamond": "Diamond",
        "item.minecraft.gold_ingot": "Gold Ingot",
        "block.minecraft.stone": "Stone",
        "item.minecraft.apple": "Apple",
    }


@pytest.fixture
def sample_en_us_lang_content() -> str:
    return "item.diamond.name=Diamond\nitem.gold_ingot.name=Gold Ingot\nblock.stone.name=Stone\nitem.apple.name=Apple\n"


@pytest.fixture
def sample_mcfunction_content() -> str:
    return (
        'tellraw @a {"text":"Welcome to the server!"}\n'
        'data modify storage minecraft:translations messages.player_joined set value "Player joined the game"\n'
        "say Game started\n"
        'data modify storage minecraft:translations messages.welcome set value "Welcome to the arena!"\n'
        'data modify storage minecraft:translations messages.goodbye set value "Goodbye, see you next time!"\n'
    )


@pytest.fixture
def temp_mods_dir(tmp_path: Path) -> Path:
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    return mods_dir


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    return out_dir


@pytest.fixture
def temp_work_dir(tmp_path: Path) -> Path:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    return work_dir


@pytest.fixture
def sample_jar(temp_mods_dir: Path, sample_en_us_json: dict) -> Path:
    jar_path = temp_mods_dir / "test_mod.jar"
    tmp_jar_dir = temp_mods_dir / "_build_jar"
    tmp_jar_dir.mkdir()

    assets_dir = tmp_jar_dir / "assets" / "testmod" / "lang"
    assets_dir.mkdir(parents=True)
    lang_file = assets_dir / "en_us.json"
    lang_file.write_text(json.dumps(sample_en_us_json, indent=2), encoding="utf-8")

    with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(tmp_jar_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = os.path.relpath(file_path, tmp_jar_dir)
                zf.write(file_path, arcname)

    shutil.rmtree(tmp_jar_dir)
    return jar_path


@pytest.fixture
def sample_json_with_comments() -> str:
    return """{
    // This is a single-line comment
    "item.minecraft.diamond": "Diamond",
    /* This is a multi-line
       comment block */
    "item.minecraft.gold_ingot": "Gold Ingot"
}"""


@pytest.fixture
def clean_sample_en_us_json_path(tmp_path: Path, sample_en_us_json: dict) -> Path:
    path = tmp_path / "en_us.json"
    path.write_text(json.dumps(sample_en_us_json, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def sample_en_us_lang_file(tmp_path: Path, sample_en_us_lang_content: str) -> Path:
    path = tmp_path / "en_US.lang"
    path.write_text(sample_en_us_lang_content, encoding="utf-8")
    return path


@pytest.fixture
def sample_mcfunction_file(tmp_path: Path, sample_mcfunction_content: str) -> Path:
    path = tmp_path / "test.mcfunction"
    path.write_text(sample_mcfunction_content, encoding="utf-8")
    return path
