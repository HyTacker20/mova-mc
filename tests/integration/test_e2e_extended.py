"""Additional E2E integration tests — dry-run, multi-mod, hint lang."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from app.application.pipeline import PipelineContext, run_pipeline
from app.core.settings import Settings
from app.domain.models import Mod
from app.infrastructure.providers.openai_like import OpenAILikeProvider
from app.utils.progress import ProgressReporter


class NullProgress(ProgressReporter):
    def report(self, _event: str, **_data: object) -> None:
        return None


def _build_sample_jar(tmp_path: Path, name: str = "test_mod.jar") -> Path:
    mods_path = tmp_path / "mods"
    mods_path.mkdir(exist_ok=True)
    jar_path = mods_path / name
    payload = json.dumps(
        {
            "block.minecraft.stone": "Stone",
            "item.minecraft.apple": "Apple",
            "item.minecraft.diamond": "Diamond",
        },
        indent=4,
    ).replace("\n", "\r\n")
    with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("assets/testmod/lang/en_us.json", payload)
    return jar_path


def _make_settings(mods_path: Path, workspace: Path, output: Path, **overrides: object) -> Settings:
    s = Settings()
    s.mods_path = str(mods_path)
    s.temp_path = str(workspace)
    s.translation_path = str(output)
    s.source_mc_lang = "en_US"
    s.target_mc_lang = "es_ES"
    s.max_workers = 1
    s.provider = "openai"
    s.output_mode = "separate"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _echo_provider() -> OpenAILikeProvider:
    transport = MagicMock()
    transport.complete.side_effect = lambda messages, **_kw: messages[-1]["content"]
    return OpenAILikeProvider(
        source_lang="en",
        target_lang="es",
        transport=transport,
        service_name="e2e",
        capitalize=False,
        max_retries=0,
    )


class TestE2EAdditional:
    def test_multiple_mods_all_translated(self, tmp_path: Path) -> None:
        """Pipeline handles multiple JARs and produces output for each."""
        jar1 = _build_sample_jar(tmp_path, "mod_a.jar")
        jar2 = _build_sample_jar(tmp_path, "mod_b.jar")
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()
        settings = _make_settings(tmp_path / "mods", ws, out)
        ctx = PipelineContext(settings=settings, progress=NullProgress(), provider=_echo_provider(), workspace=ws)
        mods = [
            Mod(name=jar1.name, path=jar1, selected=True),
            Mod(name=jar2.name, path=jar2, selected=True),
        ]
        run_pipeline(ctx, mods)
        assert (out / "mod_a.jar").exists()
        assert (out / "mod_b.jar").exists()

    def test_unselected_mod_not_in_output(self, tmp_path: Path) -> None:
        """Unselected mods do not appear in the output directory."""
        jar1 = _build_sample_jar(tmp_path, "selected.jar")
        jar2 = _build_sample_jar(tmp_path, "skipped.jar")
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()
        settings = _make_settings(tmp_path / "mods", ws, out)
        ctx = PipelineContext(settings=settings, progress=NullProgress(), provider=_echo_provider(), workspace=ws)
        mods = [
            Mod(name=jar1.name, path=jar1, selected=True),
            Mod(name=jar2.name, path=jar2, selected=False),
        ]
        run_pipeline(ctx, mods)
        assert (out / "selected.jar").exists()
        assert not (out / "skipped.jar").exists()

    def test_translated_files_have_correct_structure(self, tmp_path: Path) -> None:
        """Translated JAR preserves original structure with target language file."""
        jar = _build_sample_jar(tmp_path)
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()
        settings = _make_settings(jar.parent, ws, out)
        ctx = PipelineContext(settings=settings, progress=NullProgress(), provider=_echo_provider(), workspace=ws)
        mods = [Mod(name=jar.name, path=jar, selected=True)]
        run_pipeline(ctx, mods)

        with zipfile.ZipFile(out / jar.name, "r") as zf:
            names = zf.namelist()
        # Original en_US.json preserved, target es_es.json added
        assert any("en_us" in n.lower() for n in names)
        assert any("es_es" in n.lower() for n in names)

    def test_empty_jar_creates_no_output(self, tmp_path: Path) -> None:
        """A JAR with no language files produces no output."""
        jar = tmp_path / "mods" / "empty.jar"
        jar.parent.mkdir()
        with zipfile.ZipFile(jar, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()
        settings = _make_settings(jar.parent, ws, out)
        ctx = PipelineContext(settings=settings, progress=NullProgress(), provider=_echo_provider(), workspace=ws)
        mods = [Mod(name=jar.name, path=jar, selected=True)]
        run_pipeline(ctx, mods)
        # No output jar since there was nothing to translate
        assert not (out / jar.name).exists()

    def test_resourcepack_output_mode(self, tmp_path: Path) -> None:
        """Full pipeline with output_mode=resourcepack produces a valid resource pack .zip."""
        jar = _build_sample_jar(tmp_path)
        ws = tmp_path / "ws"
        out = tmp_path / "out"
        ws.mkdir()
        out.mkdir()
        settings = _make_settings(jar.parent, ws, out, output_mode="resourcepack")
        ctx = PipelineContext(settings=settings, progress=NullProgress(), provider=_echo_provider(), workspace=ws)
        mods = [Mod(name=jar.name, path=jar, selected=True)]
        run_pipeline(ctx, mods)

        pack_zip = out / "Spanish Spain (MovaMC).zip"
        assert pack_zip.exists(), f"Expected {pack_zip}"

        with zipfile.ZipFile(pack_zip, "r") as zf:
            names = sorted(zf.namelist())

        # pack.mcmeta must be present
        assert "pack.mcmeta" in names

        # Source-lang file must NOT be in the resource pack
        assert not any("en_us" in n.lower() for n in names)

        # Target-lang file must be present
        assert any("es_es" in n.lower() for n in names)
