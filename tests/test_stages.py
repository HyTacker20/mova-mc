"""Tests for application pipeline stages — focus on translate stage edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.pipeline import PipelineContext
from app.application.ports import TranslationProvider
from app.application.stages.translate import stage_translate
from app.core.settings import Settings
from app.domain.models import LangFile, Mod, TranslationResult, TranslationUnit
from app.utils.progress import ProgressReporter


@pytest.fixture
def settings() -> Settings:
    s = Settings()
    s.provider = "test"
    s.max_workers = 2
    s.translation_path = str(Path("/tmp/out"))
    s.debug = False
    return s


@pytest.fixture
def progress() -> ProgressReporter:
    return ProgressReporter()


@pytest.fixture
def provider() -> MagicMock:
    p = MagicMock(spec=TranslationProvider)
    p.translate_batch.side_effect = lambda units: [
        TranslationResult(unit=u, translated_text=f"tr({u.source_text})", success=True)
        for u in units
    ]
    return p


def _make_mod(
    name: str = "test.jar",
    units: list[TranslationUnit] | None = None,
    selected: bool = True,
) -> Mod:
    if units is None:
        units = [
            TranslationUnit(key="k1", source_text="Hello", file_type="json"),
            TranslationUnit(key="k2", source_text="World", file_type="json"),
        ]
    lang_file = LangFile(
        mod_name=name,
        source_path=Path("assets/lang/en_us.json"),
        target_path=Path("assets/lang/es_es.json"),
        file_type="json",
        units=tuple(units),
    )
    return Mod(name=name, path=Path(name), lang_files=(lang_file,), selected=selected)


def _ctx(settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path | None = None) -> PipelineContext:
    ws = Path(tmp_path or "/tmp") / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return PipelineContext(settings=settings, progress=progress, provider=provider, workspace=ws)


class TestTranslateStage:
    def test_translates_all_entries(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        ctx = _ctx(settings, progress, provider, tmp_path)
        mod = _make_mod()
        result = stage_translate(ctx, [mod])

        assert len(result) == 1
        assert result[0].lang_files[0].units
        for u in result[0].lang_files[0].units:
            assert u.success

    def test_empty_lang_files_skipped(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        """Mods with no lang files are passed through unchanged."""
        mod = Mod(name="empty.jar", path=Path("empty.jar"), lang_files=(), selected=True)
        ctx = _ctx(settings, progress, provider, tmp_path)
        result = stage_translate(ctx, [mod])
        assert result[0].lang_files == ()

    def test_empty_translation_units(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        """LangFile with no TranslationUnits creates no translated units."""
        lang_file = LangFile(
            mod_name="test.jar",
            source_path=Path("en_us.json"),
            target_path=Path("es_es.json"),
            file_type="json",
            units=(),
        )
        mod = Mod(name="test.jar", path=Path("test.jar"), lang_files=(lang_file,), selected=True)
        ctx = _ctx(settings, progress, provider, tmp_path)
        result = stage_translate(ctx, [mod])
        assert result[0].lang_files[0].units == ()

    def test_unselected_mods_are_passed_through(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        mod = _make_mod(selected=False)
        ctx = _ctx(settings, progress, provider, tmp_path)
        result = stage_translate(ctx, [mod])
        # Unselected mod should not have its lang files translated
        assert result[0].selected is False
        provider.translate_batch.assert_not_called()

    def test_batch_translate_error_falls_back(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        """When translate_batch raises, original text is used as fallback."""
        provider.translate_batch.side_effect = Exception("API unavailable")
        ctx = _ctx(settings, progress, provider, tmp_path)
        mod = _make_mod()
        result = stage_translate(ctx, [mod])
        units = result[0].lang_files[0].units
        # Text is preserved but marked as failed
        assert all(u.translated_text == u.unit.source_text for u in units)
        assert all(not u.success for u in units)

    def test_batch_translate_partial_results(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        """Provider returns fewer results than input — missing units use original text."""

        def partial(units):
            return [
                TranslationResult(unit=units[0], translated_text="tr(Hello)", success=True),
                TranslationResult(unit=units[1], translated_text=units[1].source_text, success=False),
            ]

        provider.translate_batch.side_effect = partial
        ctx = _ctx(settings, progress, provider, tmp_path)
        mod = _make_mod()
        result = stage_translate(ctx, [mod])
        units = {u.unit.key: u for u in result[0].lang_files[0].units}
        assert units["k1"].translated_text == "tr(Hello)"
        assert units["k2"].translated_text == "World"  # fallback to original

    def test_effective_source_lang_logging(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        """Mod with _effective_source_lang attribute logs it but still translates."""
        mod = _make_mod()
        object.__setattr__(mod, "_effective_source_lang", "en_GB")
        ctx = _ctx(settings, progress, provider, tmp_path)
        result = stage_translate(ctx, [mod])
        assert len(result[0].lang_files[0].units) == 2

    def test_debug_mode_dumps_report(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        settings.debug = True
        settings.translation_path = str(tmp_path)
        ctx = _ctx(settings, progress, provider, tmp_path)
        mod = _make_mod()
        stage_translate(ctx, [mod])
        # Report file should exist
        reports = list(tmp_path.glob("translation_report_*.txt"))
        assert len(reports) >= 1
        content = reports[0].read_text(encoding="utf-8")
        assert "Hello" in content
        assert "tr(Hello)" in content

    def test_debug_report_oserror_handled(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        """If the report file cannot be written, the stage does not crash."""
        settings.debug = True
        settings.translation_path = "/nonexistent_dir_xyz/out"
        ctx = _ctx(settings, progress, provider, tmp_path)
        mod = _make_mod()
        # Should not raise
        stage_translate(ctx, [mod])

    def test_multiple_mods_with_one_unselected(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        mod1 = _make_mod(name="mod1.jar")
        mod2 = _make_mod(name="mod2.jar", selected=False)
        mod3 = _make_mod(name="mod3.jar")
        ctx = _ctx(settings, progress, provider, tmp_path)
        result = stage_translate(ctx, [mod1, mod2, mod3])
        assert len(result) == 3
        assert result[0].lang_files[0].units
        assert result[1].lang_files == mod2.lang_files  # unchanged
        assert result[2].lang_files[0].units

    def test_multiple_files_per_mod(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        units1 = [TranslationUnit(key="a", source_text="A", file_type="json")]
        units2 = [TranslationUnit(key="b", source_text="B", file_type="lang")]
        lf1 = LangFile(mod_name="m", source_path=Path("en.json"), target_path=Path("es.json"), file_type="json", units=tuple(units1))
        lf2 = LangFile(mod_name="m", source_path=Path("en.lang"), target_path=Path("es.lang"), file_type="lang", units=tuple(units2))
        mod = Mod(name="multi.jar", path=Path("multi.jar"), lang_files=(lf1, lf2), selected=True)
        ctx = _ctx(settings, progress, provider, tmp_path)
        result = stage_translate(ctx, [mod])
        assert len(result[0].lang_files) == 2
        assert len(result[0].lang_files[0].units) == 1
        assert len(result[0].lang_files[1].units) == 1

    def test_stage_translate_async(self, settings: Settings, progress: ProgressReporter, provider: MagicMock, tmp_path: Path) -> None:
        import asyncio

        from app.application.stages.translate import stage_translate_async

        ctx = _ctx(settings, progress, provider, tmp_path)
        mod = _make_mod()
        result = asyncio.run(stage_translate_async(ctx, [mod]))
        assert len(result) == 1
        assert result[0].lang_files[0].units
