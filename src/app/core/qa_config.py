"""QA judge configuration — extracted from Settings to eliminate duplication.

The QA config was previously parsed twice in ``Settings._apply_config_data``
(once from a ``[qa]`` table, once from flat keys).  This dataclass consolidates
both parsing paths and adds validation so ``max_workers=-1`` or a missing
threshold cannot silently propagate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _none_if_blank(raw: Any) -> str | None:
    """Return None if *raw* is None or an empty string, else str(raw)."""
    if raw is None:
        return None
    s = str(raw)
    return s if s else None


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
    def from_dict(cls, data: dict[str, Any], *, flat: bool = True) -> QaConfig:
        """Build from flat keys or a ``[qa]`` TOML table."""
        if flat:
            return cls(
                enabled=bool(data.get("qa_judge", False)),
                provider=data.get("qa_judge_provider"),
                model=_none_if_blank(data.get("qa_judge_model")),
                corrector_model=data.get("qa_corrector_model"),
                threshold=int(data.get("qa_threshold", 3)),
                max_attempts=int(data.get("qa_max_attempts", 2)),
                chunk_size=int(data.get("qa_chunk_size", 25)),
                judge_workers=int(data.get("qa_judge_workers", 2)),
            )
        else:
            enabled_raw = data.get("judge", data.get("enabled", False))
            provider_raw = data.get("judge_provider", data.get("provider"))
            model_raw = data.get("judge_model", data.get("model"))
            return cls(
                enabled=bool(enabled_raw),
                provider=provider_raw,
                model=_none_if_blank(model_raw),
                corrector_model=data.get("corrector_model"),
                threshold=int(data.get("threshold", 3)),
                max_attempts=int(data.get("max_attempts", 2)),
                chunk_size=int(data.get("chunk_size", 25)),
                judge_workers=int(data.get("judge_workers", 2)),
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
