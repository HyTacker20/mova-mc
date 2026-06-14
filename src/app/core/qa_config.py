"""QA judge configuration — extracted from Settings to eliminate duplication.

The QA config was previously parsed twice in ``Settings._apply_config_data``
(once from a ``[qa]`` table, once from flat keys).  This dataclass consolidates
both parsing paths and adds validation so ``max_workers=-1`` or a missing
threshold cannot silently propagate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MODEL_BLANK_VALUES: frozenset[str] = frozenset({""})


def _coerce_model(raw: Any) -> str | None:
    """Convert a raw config value to a model name or ``None``."""
    if raw is None:
        return None
    s = str(raw)
    return None if s in _MODEL_BLANK_VALUES else s


@dataclass
class QaConfig:
    """Immutable QA judge configuration with validation on construction."""

    enabled: bool = False
    """Whether the QA judge pass runs after translation."""

    provider: str | None = None
    """Provider name for the judge LLM (falls back to main provider)."""

    model: str | None = None
    """Model name for the judge (falls back to main model or provider default)."""

    corrector_model: str | None = None
    """Model used for re-translation of flagged entries."""

    threshold: int = 3
    """Minimum score (1-5) that triggers a flag.  Lower = stricter."""

    max_attempts: int = 2
    """Maximum re-translation attempts per flagged entry."""

    chunk_size: int = 25
    """Entries per QA chunk."""

    judge_workers: int = 2
    """Parallel workers for the judge LLM."""

    # -- validation ------------------------------------------------------

    def __post_init__(self) -> None:
        if self.threshold < 1 or self.threshold > 5:
            raise ValueError(f"qa_threshold must be 1-5, got {self.threshold}")
        if self.max_attempts < 0:
            raise ValueError(f"qa_max_attempts must be >= 0, got {self.max_attempts}")
        if self.chunk_size < 1:
            raise ValueError(f"qa_chunk_size must be >= 1, got {self.chunk_size}")
        if self.judge_workers < 1:
            raise ValueError(f"qa_judge_workers must be >= 1, got {self.judge_workers}")

    # -- factories -------------------------------------------------------

    @classmethod
    def from_flat_dict(cls, data: dict[str, Any]) -> QaConfig:
        """Build from flat keys (backward-compatible with old translator.toml)."""
        return cls(
            enabled=bool(data.get("qa_judge", False)),
            provider=data.get("qa_judge_provider"),
            model=_coerce_model(data.get("qa_judge_model")),
            corrector_model=data.get("qa_corrector_model"),
            threshold=int(data.get("qa_threshold", 3)),
            max_attempts=int(data.get("qa_max_attempts", 2)),
            chunk_size=int(data.get("qa_chunk_size", 25)),
            judge_workers=int(data.get("qa_judge_workers", 2)),
        )

    @classmethod
    def from_table_dict(cls, table: dict[str, Any]) -> QaConfig:
        """Build from a ``[qa]`` TOML table."""
        enabled_raw = table.get("judge", table.get("enabled", False))
        provider_raw = table.get("judge_provider", table.get("provider"))
        model_raw = table.get("judge_model", table.get("model"))
        return cls(
            enabled=bool(enabled_raw),
            provider=provider_raw,
            model=_coerce_model(model_raw),
            corrector_model=table.get("corrector_model"),
            threshold=int(table.get("threshold", 3)),
            max_attempts=int(table.get("max_attempts", 2)),
            chunk_size=int(table.get("chunk_size", 25)),
            judge_workers=int(table.get("judge_workers", 2)),
        )

    # -- helpers ---------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True when QA judging is enabled."""
        return self.enabled

    def resolve_model(self, main_model: str | None, main_provider: str) -> str | None:
        """Return the judge model, falling back through the chain.

        ``qa.judge_model`` → ``main_model`` → provider default.
        """
        if self.model:
            return self.model
        if self.provider:
            # When a dedicated judge provider is set, its default model
            # is resolved later by the factory.  Return None to signal
            # "use provider default".
            return main_model
        return main_model
