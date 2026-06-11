"""Pydantic DTOs for the web API.

The request schema intentionally mirrors the movamc.toml config structure so
that ``Settings(config_data=req.to_settings_dict())`` works without extra
mapping logic.  Adding a new setting = add a field here + one key in
to_settings_dict().
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QaRequest(BaseModel):
    enabled: bool = False
    provider: str | None = None
    model: str | None = None
    threshold: int = 3
    max_attempts: int = 2
    streaming: bool = True
    chunk_size: int = 25
    judge_workers: int = 2


class RateLimitRequest(BaseModel):
    rpm: float | None = None
    burst: float | None = None
    judge_rpm: float | None = None
    judge_burst: float | None = None


class JobRequest(BaseModel):
    source: str = "en_US"
    target: str = "uk_UA"
    provider: str = "google"
    model: str | None = None
    workers: int = Field(default=4, ge=1, le=32)

    path: str = "./mods"
    output: str = "./translated_mods"
    output_mode: str = "separate"

    no_cache: bool = False
    dry_run: bool = False
    hint_lang: str | None = None
    glossary_path: str | None = None
    chunk_mode: str = "auto"
    chunk_size: int | None = None
    chunk_token_budget: int = 3500
    progress_batch_size: int = 10

    selected_mods: list[str] = Field(default_factory=list)

    qa: QaRequest = Field(default_factory=QaRequest)
    rate_limit: RateLimitRequest = Field(default_factory=RateLimitRequest)

    def to_settings_dict(self) -> dict[str, Any]:
        """Convert to config_data dict consumed by Settings(config_data=...)."""
        d: dict[str, Any] = {
            "source": self.source,
            "target": self.target,
            "provider": self.provider,
            "workers": self.workers,
            "output": self.output,
            "path": self.path,
            "no_cache": self.no_cache,
            "output_mode": self.output_mode,
            "chunk_mode": self.chunk_mode,
            "chunk_token_budget": self.chunk_token_budget,
            "progress_batch_size": self.progress_batch_size,
            "qa": {
                "judge": self.qa.enabled,
                "judge_provider": self.qa.provider,
                "judge_model": self.qa.model,
                "threshold": self.qa.threshold,
                "max_attempts": self.qa.max_attempts,
                "streaming": self.qa.streaming,
                "chunk_size": self.qa.chunk_size,
                "judge_workers": self.qa.judge_workers,
            },
        }
        if self.model:
            d["model"] = self.model
        if self.hint_lang:
            d["hint_lang"] = self.hint_lang
        if self.glossary_path:
            d["glossary_path"] = self.glossary_path
        if self.chunk_size is not None:
            d["chunk_size"] = self.chunk_size
        if self.dry_run:
            d["dry_run"] = True

        rate: dict[str, Any] = {}
        if self.rate_limit.rpm is not None:
            rate["rpm"] = self.rate_limit.rpm
        if self.rate_limit.burst is not None:
            rate["burst"] = self.rate_limit.burst
        if self.rate_limit.judge_rpm is not None or self.rate_limit.judge_burst is not None:
            judge: dict[str, float] = {}
            if self.rate_limit.judge_rpm is not None:
                judge["rpm"] = self.rate_limit.judge_rpm
            if self.rate_limit.judge_burst is not None:
                judge["burst"] = self.rate_limit.judge_burst
            rate["judge"] = judge
        if rate:
            d["rate_limit"] = rate

        return d


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str


class FileStatsResponse(BaseModel):
    path: str
    file_type: str
    entries_total: int
    entries_translated: int
    entries_failed: int


class ModStatsResponse(BaseModel):
    name: str
    skipped: bool
    translated_entries: int
    total_entries: int
    failed_entries: int
    files: list[FileStatsResponse]


class OverallStatsResponse(BaseModel):
    provider: str
    source_lang: str
    target_lang: str
    translated_mods: int
    total_mods: int
    translated_entries: int
    total_entries: int
    failed_entries: int
    duration_seconds: float
    mods: list[ModStatsResponse]


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    error: str | None = None
    stats: OverallStatsResponse | None = None


class ModInfoResponse(BaseModel):
    name: str
    size_bytes: int
    has_lang_files: bool
    lang_file_count: int
    estimated_entries: int
    selected: bool


class ScanResponse(BaseModel):
    mods: list[ModInfoResponse]
    total: int
    selected: int


class ProviderInfo(BaseModel):
    id: str
    label: str
    requires_key: bool
    key_env: str | None = None
    default_model: str | None = None
    models: list[str] = Field(default_factory=list)


class CatalogResponse(BaseModel):
    providers: list[ProviderInfo]
