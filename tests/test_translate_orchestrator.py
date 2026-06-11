import argparse
import builtins
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.infrastructure.providers.registry import check_provider_available
from app.interfaces.cli.args import add_translate_arguments
from app.interfaces.cli.main import _resolve_provider


class TestCheckProviderAvailable:
    def test_google_available(self):
        ok, _message = check_provider_available("google")
        assert ok is True

    def test_google_not_installed(self):
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "deep_translator":
                raise ImportError("No module named 'deep_translator'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            ok, _msg = check_provider_available("google")
            assert ok is False

    def test_openai_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            ok, _msg = check_provider_available("openai")
            assert ok is False

    def test_unknown_provider(self):
        ok, _msg = check_provider_available("nonexistent")
        assert ok is False


class TestResolveProvider:
    def test_default_provider(self):
        args = argparse.Namespace(provider="google", ai=False)
        result = _resolve_provider(args)
        assert result == "google"

    def test_ai_flag_deprecated(self):
        args = argparse.Namespace(provider="google", ai=True)
        result = _resolve_provider(args)
        assert result == "openai"
        assert args.ai is False

    def test_openai_explicit(self):
        args = argparse.Namespace(provider="openai", ai=False)
        result = _resolve_provider(args)
        assert result == "openai"


class TestAddTranslateArguments:
    def test_all_flags(self):
        parser = argparse.ArgumentParser()
        add_translate_arguments(parser)
        args = parser.parse_args(
            [
                "-p",
                "./mods",
                "-s",
                "en_US",
                "-t",
                "uk_UA",
                "-o",
                "./out",
                "--provider",
                "openai",
                "--workers",
                "6",
                "--dry-run",
            ]
        )
        assert args.path == "./mods"
        assert args.source == "en_US"
        assert args.target == "uk_UA"
        assert args.output == "./out"
        assert args.provider == "openai"
        assert args.workers == 6
        assert args.dry_run is True

    def test_deprecated_ai_flag(self):
        parser = argparse.ArgumentParser()
        add_translate_arguments(parser)
        args = parser.parse_args(
            [
                "-p",
                "./mods",
                "-s",
                "en_US",
                "-t",
                "uk_UA",
                "-o",
                "./out",
                "--ai",
                "--workers",
                "6",
                "--dry-run",
            ]
        )
        assert args.ai is True

    def test_defaults(self):
        parser = argparse.ArgumentParser()
        add_translate_arguments(parser)
        args = parser.parse_args([])
        assert args.path == "./mods"
        assert args.source is None
        assert args.target is None
        assert args.output is None
        assert args.provider == "google"
        assert args.workers == 4
        assert args.dry_run is False


class TestPipeline:
    def test_build_context_creates_provider(self, tmp_path: Path):
        from app.application.pipeline import build_context
        from app.core.settings import Settings

        settings = Settings()
        settings.provider = "google"
        settings.temp_path = str(tmp_path / "temp")
        settings.translation_path = str(tmp_path / "out")

        progress = MagicMock()
        ctx = build_context(settings, progress, cache_path=str(tmp_path / "cache.db"))

        assert ctx.settings is settings
        assert ctx.provider is not None
        assert ctx.workspace == Path(settings.temp_path)
        progress.report.assert_not_called()

    def test_run_pipeline_dry_run_no_mods(self, tmp_path: Path):
        from app.application.pipeline import PipelineContext, run_pipeline
        from app.core.settings import Settings

        settings = Settings()
        settings.temp_path = str(tmp_path / "temp")
        settings.translation_path = str(tmp_path / "out")
        (tmp_path / "temp").mkdir()

        progress = MagicMock()
        ctx = PipelineContext(
            settings=settings,
            progress=progress,
            provider=MagicMock(),
            workspace=Path(settings.temp_path),
        )

        result = run_pipeline(ctx, [])
        assert result.stats.total_mods == 0
