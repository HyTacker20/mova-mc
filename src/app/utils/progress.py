from collections.abc import Callable
from typing import Any

from .qa_log import log_qa_event


class ProgressReporter:
    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def subscribe(self, callback: Callable[..., None]) -> None:
        self._callbacks.append(callback)

    def report(self, event: str, **data: Any) -> None:
        self._notify(event, **data)

    def _notify(self, event: str, **kwargs: Any) -> None:
        if event.startswith("qa_"):
            log_qa_event(event, **kwargs)
        for cb in self._callbacks:
            cb(event, **kwargs)

    def report_title(self, title: str) -> None:
        self._notify("title", text=title)

    def report_message(self, message: str) -> None:
        self._notify("message", text=message)

    def report_error(self, error: str) -> None:
        self._notify("error", text=error)

    def report_complete(self, output_path: str) -> None:
        self._notify("complete", output_path=output_path)

    def report_scan_start(self, total: int) -> None:
        self._notify("scan_start", total=total)

    def report_scan_progress(self, current: int, total: int, name: str) -> None:
        self._notify("scan_progress", current=current, total=total, name=name)

    def report_scan_complete(self, total: int) -> None:
        self._notify("scan_complete", total=total)

    def report_mod_start(self, mod_name: str, file_count: int, entry_count: int) -> None:
        self._notify("mod_start", mod_name=mod_name, file_count=file_count, entry_count=entry_count)

    def report_mod_file_start(self, mod_name: str, file_path: str, entry_count: int) -> None:
        self._notify("mod_file_start", mod_name=mod_name, file_path=file_path, entry_count=entry_count)

    def report_mod_file_progress(self, mod_name: str, file_path: str, current: int, total: int) -> None:
        self._notify("mod_file_progress", mod_name=mod_name, file_path=file_path, current=current, total=total)

    def report_mod_file_complete(self, mod_name: str, file_path: str, duration_ms: int, errors: int) -> None:
        self._notify(
            "mod_file_complete",
            mod_name=mod_name,
            file_path=file_path,
            duration_ms=duration_ms,
            errors=errors,
        )

    def report_mod_complete(self, mod_name: str, translated: int, total: int, failed: int) -> None:
        self._notify("mod_complete", mod_name=mod_name, translated=translated, total=total, failed=failed)

    def report_overall_progress(
        self,
        completed_mods: int,
        total_mods: int,
        completed_entries: int,
        total_entries: int,
        fractional_mods: float | None = None,
    ) -> None:
        self._notify(
            "overall_progress",
            completed_mods=completed_mods,
            fractional_mods=fractional_mods,
            total_mods=total_mods,
            completed_entries=completed_entries,
            total_entries=total_entries,
        )

    def report_repack_start(self, total: int) -> None:
        self._notify("repack_start", total=total)

    def report_repack_progress(self, current: int, total: int, name: str) -> None:
        self._notify("repack_progress", current=current, total=total, name=name)

    def report_repack_complete(self, total: int) -> None:
        self._notify("repack_complete", total=total)

    def report_progress(self, current: int, total: int, item: str = "") -> None:
        self._notify("progress", current=current, total=total, item=item)

    def report_entry_progress(self, done: int, total: int, mod_name: str = "", file_path: str = "") -> None:
        self._notify(
            "entry_progress",
            done=done,
            total=total,
            mod_name=mod_name,
            file_path=file_path,
        )

    def report_translated_entry(self, key: str, source: str, translated: str, mod_name: str = "") -> None:
        self._notify(
            "translated_entry",
            key=key,
            source=source,
            translated=translated,
            mod_name=mod_name,
        )

    # ── QA events ──────────────────────────────────────────────────────

    def report_qa_progress(self, done: int, total: int) -> None:
        self._notify("qa_progress", done=done, total=total)

    def report_qa_start(self, total: int, provider: str, model: str) -> None:
        self._notify("qa_start", total=total, provider=provider, model=model)

    def report_qa_verdict(
        self,
        key: str,
        score: int,
        is_flagged: bool,
        issue: str | None = None,
    ) -> None:
        self._notify(
            "qa_verdict",
            key=key,
            score=score,
            is_flagged=is_flagged,
            issue=issue,
        )

    def report_qa_correction(
        self,
        key: str,
        accepted: bool,
        attempt: int,
        max_attempts: int,
    ) -> None:
        self._notify(
            "qa_correction",
            key=key,
            accepted=accepted,
            attempt=attempt,
            max_attempts=max_attempts,
        )

    def report_qa_done(self, flagged: int, corrected: int) -> None:
        self._notify("qa_done", flagged=flagged, corrected=corrected)

    def report_qa_warning(self, key: str, message: str) -> None:
        self._notify("qa_warning", key=key, message=message)
