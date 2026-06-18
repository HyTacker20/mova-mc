from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.application.pipeline import PipelineContext, run_pipeline
from app.core.settings import Settings
from app.domain.models import Mod
from app.infrastructure.providers.openai_like import OpenAILikeProvider
from app.utils.progress import ProgressReporter


class RecordingProgress(ProgressReporter):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, dict[str, object]]] = []

    def report(self, event: str, **data: object) -> None:
        self.events.append((event, data))


def _build_settings(mods_path: Path, temp_path: Path, output_path: Path) -> Settings:
    settings = Settings()
    settings.paths.mods_path = str(mods_path)
    settings.temp_path = str(temp_path)
    settings.paths.translation_path = str(output_path)
    settings.source_mc_lang = "en_US"
    settings.target_mc_lang = "es_ES"
    settings.source_google_lang = "en"
    settings.target_google_lang = "es"
    settings.max_workers = 2
    settings.provider = "openai"
    settings.paths.output_mode = "separate"
    return settings


def _build_provider() -> OpenAILikeProvider:
    import json as _json

    transport = MagicMock()

    def _translate_response(messages, **_kwargs):
        content = messages[-1]["content"]
        if content.strip().startswith("{"):
            # Chunk translation — return a JSON object with tr_ prefixed values
            parsed = _json.loads(content)
            return _json.dumps({k: f"tr_{v}" for k, v in parsed.items()}, ensure_ascii=False)
        # Single-item translation
        return f"tr_{content.replace('Translate: ', '')}"

    transport.complete.side_effect = _translate_response
    transport.acomplete = AsyncMock(side_effect=_translate_response)
    return OpenAILikeProvider(
        source_lang="en",
        target_lang="es",
        transport=transport,
        service_name="integration",
        capitalize=True,
        max_retries=0,
    )


def test_pipeline_cleans_stale_workspace_at_start(sample_jar: Path, tmp_path: Path) -> None:
    """run_pipeline removes stale directories from the workspace before unpacking."""
    mods_path = sample_jar.parent
    workspace = tmp_path / "workspace"
    output_path = tmp_path / "translated_mods"
    workspace.mkdir()
    output_path.mkdir()

    # Pre-populate the workspace with a stale dir (simulates crashed previous run)
    stale_dir = workspace / "stale_mod"
    stale_dir.mkdir()
    (stale_dir / "leftover.txt").write_text("garbage", encoding="utf-8")

    settings = _build_settings(mods_path, workspace, output_path)
    progress = RecordingProgress()
    provider = _build_provider()
    ctx = PipelineContext(settings=settings, progress=progress, provider=provider, workspace=workspace)

    mods = [Mod(name=sample_jar.name, path=sample_jar, selected=True)]
    run_pipeline(ctx, mods)

    # Workspace should NOT contain the stale dir after pipeline run
    assert not (workspace / "stale_mod").exists()
    # The valid mod workspace dir should exist (unpacked)
    assert workspace.exists()


def test_pipeline_translates_jar(sample_jar: Path, tmp_path: Path) -> None:
    mods_path = sample_jar.parent
    workspace = tmp_path / "workspace"
    output_path = tmp_path / "translated_mods"
    workspace.mkdir()
    output_path.mkdir()

    settings = _build_settings(mods_path, workspace, output_path)
    progress = RecordingProgress()
    provider = _build_provider()
    ctx = PipelineContext(settings=settings, progress=progress, provider=provider, workspace=workspace)

    mods = [Mod(name=sample_jar.name, path=sample_jar, selected=True)]
    result = run_pipeline(ctx, mods)

    output_jar = output_path / sample_jar.name
    assert output_jar.exists()
    assert result.stats.total_entries == 4
    assert result.stats.failed_entries == 0

    with zipfile.ZipFile(output_jar, "r") as zf:
        names = [name for name in zf.namelist() if not name.endswith("/")]
        assert "assets/testmod/lang/es_es.json" in names
        payload = json.loads(zf.read("assets/testmod/lang/es_es.json").decode("utf-8"))

    assert payload["item.minecraft.diamond"] == "Tr_Diamond"
    assert payload["item.minecraft.gold_ingot"] == "Tr_Gold Ingot"
    assert payload["block.minecraft.stone"] == "Tr_Stone"
    assert payload["item.minecraft.apple"] == "Tr_Apple"
