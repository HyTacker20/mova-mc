"""Tests for the CLI presenter — summary formatting and JSON export."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.stats import FileStats, ModStats, OverallStats
from app.interfaces.cli.presenter import export_stats_json, format_cli_summary_lines


def _make_stats(
    mods_data: list[dict] | None = None,
    failed: int = 0,
    provider: str = "google",
    source: str = "en_US",
    target: str = "uk_UA",
) -> OverallStats:
    stats = OverallStats()
    stats.start()
    stats.provider = provider
    stats.source_lang = source
    stats.target_lang = target

    if mods_data is None:
        mods_data = [
            {"name": "test.jar", "entries": 10, "files": 2, "skipped": False},
        ]

    for md in mods_data:
        ms = ModStats(name=md["name"], skipped=md.get("skipped", False))
        for i in range(md.get("files", 1)):
            ent_per_file = md["entries"] // md["files"]
            fail_per_file = failed // md["files"]
            ms.files.append(
                FileStats(
                    path=f"file{i}.json",
                    file_type="json",
                    entries_total=ent_per_file,
                    entries_translated=ent_per_file - fail_per_file,
                    entries_failed=fail_per_file,
                    duration_ms=0,
                )
            )
        # Manually set aggregated values instead of calling finish() which uses real time
        ms.total_entries = md["entries"]
        ms.translated_entries = md["entries"] - failed
        ms.failed_entries = failed
        ms.duration_ms = md.get("ms", 0)
        stats.mods.append(ms)

    stats.total_mods = len(stats.mods)
    stats.translated_mods = sum(1 for m in stats.mods if not m.skipped)
    stats.skipped_mods = sum(1 for m in stats.mods if m.skipped)
    stats.total_entries = sum(m.total_entries for m in stats.mods)
    stats.translated_entries = sum(m.translated_entries for m in stats.mods)
    stats.failed_entries = sum(m.failed_entries for m in stats.mods)
    stats.total_duration_ms = sum(m.duration_ms for m in stats.mods)
    return stats


class TestFormatCliSummary:
    def test_contains_header_and_footer(self) -> None:
        stats = _make_stats()
        lines = format_cli_summary_lines(stats)
        assert lines[0].startswith("=")
        assert lines[-1].startswith("=")
        assert "Translation Complete" in lines[1]

    def test_shows_provider_and_languages(self) -> None:
        stats = _make_stats(provider="openai", source="en_GB", target="es_ES")
        lines = format_cli_summary_lines(stats)
        assert any("openai" in line for line in lines)
        assert any("en_GB" in line for line in lines)
        assert any("es_ES" in line for line in lines)

    def test_shows_mod_names_and_entries(self) -> None:
        stats = _make_stats([{"name": "mod_a.jar", "entries": 5, "files": 1, "ms": 200}])
        lines = format_cli_summary_lines(stats)
        assert any("mod_a.jar" in line for line in lines)
        assert any("5" in line for line in lines)

    def test_shows_skipped_mods(self) -> None:
        stats = _make_stats(
            [
                {"name": "skipped_mod.jar", "entries": 0, "files": 0, "ms": 0, "skipped": True},
            ]
        )
        lines = format_cli_summary_lines(stats)
        assert any("SKIPPED" in line for line in lines)

    def test_shows_failed_entries(self) -> None:
        stats = _make_stats(
            [{"name": "test.jar", "entries": 5, "files": 1, "ms": 100}],
            failed=2,
        )
        lines = format_cli_summary_lines(stats)
        assert any("Failed: 2" in line for line in lines)

    def test_zero_failed_shows_zero(self) -> None:
        stats = _make_stats(failed=0)
        lines = format_cli_summary_lines(stats)
        assert any("Failed: 0" in line for line in lines)

    def test_multiple_mods_total_row(self) -> None:
        stats = _make_stats(
            [
                {"name": "a.jar", "entries": 3, "files": 1, "ms": 100},
                {"name": "b.jar", "entries": 7, "files": 2, "ms": 200},
            ]
        )
        lines = format_cli_summary_lines(stats)
        totals = [line for line in lines if "TOTAL" in line]
        assert len(totals) == 1
        assert "10" in totals[0]  # 3 + 7 entries

    def test_mod_timestamps_formatted(self) -> None:
        stats = _make_stats([{"name": "m.jar", "entries": 1, "files": 1, "ms": 1500}])
        lines = format_cli_summary_lines(stats)
        assert any("1.5s" in line for line in lines)

    def test_no_mods(self) -> None:
        stats = _make_stats([])
        lines = format_cli_summary_lines(stats)
        assert "0 mods processed" in lines[1]


class TestExportStatsJson:
    def test_exports_valid_json(self, tmp_path: Path) -> None:
        stats = _make_stats()
        out = tmp_path / "stats.json"
        result = export_stats_json(stats, str(out))
        assert result is not None
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["total_mods"] == 1
        assert data["provider"] == "google"

    def test_export_oserror_returns_none(self) -> None:
        """On an invalid path, export returns None."""
        stats = _make_stats()
        result = export_stats_json(stats, "")
        assert result is None

    def test_export_creates_parent_dir(self, tmp_path: Path) -> None:
        stats = _make_stats()
        out = tmp_path / "sub" / "dir" / "stats.json"
        result = export_stats_json(stats, str(out))
        assert result is not None
        assert out.exists()

    def test_export_contains_all_mods(self, tmp_path: Path) -> None:
        stats = _make_stats(
            [
                {"name": "a.jar", "entries": 5, "files": 1, "ms": 100},
                {"name": "b.jar", "entries": 3, "files": 2, "ms": 200},
            ]
        )
        out = tmp_path / "stats.json"
        export_stats_json(stats, str(out))
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["total_mods"] == 2
        assert data["total_entries"] == 8
