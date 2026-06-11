from __future__ import annotations

from pathlib import Path

from loguru import logger

from ...domain.stats import OverallStats
from ...utils.result import Err, Ok, Result


def format_cli_summary_lines(stats: OverallStats) -> list[str]:
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append(f"  Translation Complete — {stats.total_mods} mods processed")
    lines.append("")
    lines.append(f"  {'Mod':<30} {'Entries':>8} {'Files':>7} {'Time':>8}")
    lines.append("  " + "-" * 55)
    for m in stats.mods:
        status = " SKIPPED" if m.skipped else ""
        time_s = f"{m.duration_ms / 1000:.1f}s"
        lines.append(f"  {m.name[:30]:<30} {m.total_entries:>8} {len(m.files):>7} {time_s:>8}{status}")
    lines.append("  " + "-" * 55)
    total_time = f"{stats.total_duration_ms / 1000:.1f}s"
    lines.append(f"  {'TOTAL':<30} {stats.total_entries:>8} {sum(len(m.files) for m in stats.mods):>7} {total_time:>8}")
    lines.append("")
    lines.append(f"  Provider: {stats.provider}")
    lines.append(f"  Source -> Target: {stats.source_lang} -> {stats.target_lang}")
    if stats.failed_entries > 0:
        lines.append(f"  Failed: {stats.failed_entries} entries")
    else:
        lines.append("  Failed: 0 entries")
    lines.append("=" * 50)
    return lines


def print_cli_summary(stats: OverallStats) -> None:
    for line in format_cli_summary_lines(stats):
        logger.info(line)


def export_stats_json(stats: OverallStats, path: str | Path) -> Result[Path, str]:
    import json

    export_path = Path(path)
    try:
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", encoding="utf-8") as fh:
            json.dump(stats.to_dict(), fh, indent=2, ensure_ascii=False)
        logger.info(f"Stats exported to {export_path}")
        return Ok(export_path)
    except OSError as e:
        return Err(str(e))
