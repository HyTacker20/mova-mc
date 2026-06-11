"""Backward-compatible re-export. Use infrastructure.providers.registry instead."""

from ..infrastructure.providers.registry import check_provider_available

__all__ = ["check_provider_available"]
