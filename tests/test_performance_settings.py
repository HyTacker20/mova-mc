"""Tests for performance-related settings and pipeline wiring."""

from __future__ import annotations

import argparse

from app.application.pipeline import _resolve_translation_chunk_size
from app.core.settings import Settings
from app.utils.retry_logic import TranslationRateLimiter


class TestChunkModeSettings:
    def test_default_auto_uses_provider_default(self) -> None:
        settings = Settings()
        assert _resolve_translation_chunk_size(settings) is None

    def test_item_mode_forces_per_item(self) -> None:
        settings = Settings(config_data={"chunk_mode": "item"})
        assert _resolve_translation_chunk_size(settings) == 1

    def test_chunk_token_budget_from_config(self) -> None:
        settings = Settings(config_data={"chunk_token_budget": 5000, "chunk_max_text_length": 150})
        assert settings.chunk_token_budget == 5000
        assert settings.chunk_max_text_length == 150

    def test_explicit_chunk_size(self) -> None:
        settings = Settings(config_data={"chunk_size": 10})
        assert _resolve_translation_chunk_size(settings) == 10

    def test_rate_limit_config_from_toml_section(self) -> None:
        settings = Settings(config_data={
            "rate_limit": {
                "rpm": 300,
                "burst": 20,
                "judge": {"rpm": 120, "burst": 5},
            },
        })
        assert settings.rate_limit_rpm == 300.0
        assert settings.rate_limit_burst == 20.0
        assert settings.rate_limit_services["judge"]["rpm"] == 120.0

    def test_qa_chunk_size_from_config(self) -> None:
        settings = Settings(config_data={"qa": {"chunk_size": 15, "judge_workers": 3}})
        assert settings.qa_chunk_size == 15
        assert settings.qa_judge_workers == 3


class TestRateLimiterConfigure:
    def test_configure_applies_service_overrides(self) -> None:
        limiter = TranslationRateLimiter()
        limiter.configure(rpm=300, burst=20, services={"judge": {"rpm": 120, "burst": 5}})
        bucket = limiter.get_bucket("judge")
        assert bucket._rate == 120 / 60.0
        assert bucket._burst == 5.0

    def test_workers_no_longer_force_item_mode(self) -> None:
        settings = Settings(config_data={"workers": 8})
        settings = Settings(
            cli_args=argparse.Namespace(workers=8),
            config_data={"chunk_mode": "auto"},
        )
        assert settings.max_workers == 8
        assert _resolve_translation_chunk_size(settings) is None
