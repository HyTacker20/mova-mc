"""Shared formatting helpers for TUI display."""

from __future__ import annotations


def format_duration(ms: int | float) -> str:
    """Format milliseconds as a human-readable duration string."""
    seconds = ms / 1000.0
    if seconds < 1:
        return f"{ms:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m {secs}s"


def format_duration_seconds(seconds: float) -> str:
    """Format seconds as a human-readable duration string."""
    return format_duration(seconds * 1000.0)


def estimate_eta_seconds(done: int, total: int, elapsed_s: float) -> float | None:
    """Linear ETA estimate in seconds, or None if not enough data."""
    if done <= 0 or total <= done or elapsed_s <= 1.0:
        return None
    rate = done / elapsed_s
    if rate <= 0:
        return None
    return (total - done) / rate


def format_progress_pct(current: float, total: int) -> int:
    """Return integer percentage for progress display (0-100)."""
    if total <= 0:
        return 0
    return min(100, round(current / total * 100))
