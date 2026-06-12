"""SSE formatting helpers and stats serialisation."""

from __future__ import annotations

import json
from typing import Any

from app.domain.stats import OverallStats
from backend.schemas import FileStatsResponse, ModStatsResponse, OverallStatsResponse


def sse_frame(data: dict[str, Any]) -> str:
    """Format a dict as an SSE data frame (``data: {...}\\n\\n``)."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_keepalive() -> str:
    """SSE comment line used as a keepalive ping."""
    return ": keepalive\n\n"


def serialise_stats(stats: OverallStats) -> OverallStatsResponse:
    """Convert domain OverallStats to a JSON-serialisable response model."""
    mod_responses: list[ModStatsResponse] = []
    for m in stats.mods:
        files = [
            FileStatsResponse(
                path=f.path,
                file_type=f.file_type,
                entries_total=f.entries_total,
                entries_translated=f.entries_translated,
                entries_failed=f.entries_failed,
            )
            for f in m.files
        ]
        mod_responses.append(
            ModStatsResponse(
                name=m.name,
                skipped=m.skipped,
                translated_entries=m.translated_entries,
                total_entries=m.total_entries,
                failed_entries=m.failed_entries,
                files=files,
            )
        )

    return OverallStatsResponse(
        provider=stats.provider,
        source_lang=stats.source_lang,
        target_lang=stats.target_lang,
        translated_mods=stats.translated_mods,
        total_mods=stats.total_mods,
        translated_entries=stats.translated_entries,
        total_entries=stats.total_entries,
        failed_entries=stats.failed_entries,
        duration_seconds=stats.total_duration_ms / 1000,
        mods=mod_responses,
        qa_enabled=stats.qa_enabled,
        qa_judged=stats.qa_judged,
        qa_flagged=stats.qa_flagged,
        qa_corrected=stats.qa_corrected,
        qa_warnings=stats.qa_warnings,
    )
