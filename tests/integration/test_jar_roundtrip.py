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


def _build_settings(mods_path: Path, temp_path: Path, output_path: Path) -> Settings:
    settings = Settings()
    settings.mods_path = str(mods_path)
    settings.temp_path = str(temp_path)
    settings.translation_path = str(output_path)
    settings.source_mc_lang = "en_US"
    settings.target_mc_lang = "en_US"
    settings.source_google_lang = "en"
    settings.target_google_lang = "en"
    settings.max_workers = 1
    settings.provider = "openai"
    settings.output_mode = "separate"
    return settings


def _build_echo_provider() -> OpenAILikeProvider:
    transport = MagicMock()
    transport.complete.side_effect = lambda messages, **_kwargs: messages[-1]["content"].replace("Translate: ", "")
    return OpenAILikeProvider(
        source_lang="en",
        target_lang="es",
        transport=transport,
        service_name="integration",
        capitalize=False,
        max_retries=0,
    )


def _archive_contents(path: Path) -> dict[str, bytes]:
    contents: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            contents[name] = zf.read(name)
    return contents


def test_pipeline_roundtrip_preserves_archive_contents(sample_en_us_json: dict, tmp_path: Path) -> None:
    mods_path = tmp_path / "mods"
    mods_path.mkdir()
    sample_jar = mods_path / "test_mod.jar"
    with zipfile.ZipFile(sample_jar, "w", zipfile.ZIP_DEFLATED) as zf:
        payload = json.dumps(sample_en_us_json, indent=4).replace("\n", "\r\n")
        zf.writestr(
            "assets/testmod/lang/en_us.json",
            payload,
        )

    workspace = tmp_path / "workspace"
    output_path = tmp_path / "translated_mods"
    workspace.mkdir()
    output_path.mkdir()

    settings = _build_settings(mods_path, workspace, output_path)
    ctx = PipelineContext(
        settings=settings,
        progress=NullProgress(),
        provider=_build_echo_provider(),
        workspace=workspace,
    )

    mods = [Mod(name=sample_jar.name, path=sample_jar, selected=True)]
    run_pipeline(ctx, mods)

    output_jar = output_path / sample_jar.name
    assert output_jar.exists()
    assert _archive_contents(output_jar) == _archive_contents(sample_jar)
