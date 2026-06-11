"""Rich-markup formatting for QA fields on a TranslationResult."""

from __future__ import annotations

from .models import TranslationResult


def format_provider_model(provider: str, model: str) -> str:
    """Format provider/model for display without duplicating the provider prefix."""
    if not model:
        return provider
    if not provider:
        return model
    prefix = f"{provider}/"
    if model.startswith(prefix):
        return model
    return f"{provider}/{model}"


def format_qa_correction_line(
    *,
    key: str,
    accepted: bool,
    attempt: int,
    max_attempts: int,
) -> str:
    """Plain-text line for a QA correction attempt."""
    icon = "✓" if accepted else "✗"
    if attempt == 0 and accepted:
        return f"  {icon} {key}: judge fix applied"
    return f"  {icon} {attempt}/{max_attempts} {key}"


def format_qa_rich_lines(result: TranslationResult) -> list[str]:
    """Return Rich-markup lines for QA info; empty if no QA data."""
    lines: list[str] = []

    for warning in result.qa_warnings:
        message = warning.get("message", str(warning))
        lines.append(f"    [yellow]⚡ {message}[/]")

    if result.qa_score is not None:
        score_color = (
            "green" if result.qa_score >= 4 else "yellow" if result.qa_score >= 2 else "red"
        )
        qa_info = f"[{score_color}]★ {result.qa_score}/5[/]"
        if result.qa_issue:
            qa_info += f" [dim]({result.qa_issue})[/]"
        if result.qa_attempts:
            qa_info += f" [dim]attempts={result.qa_attempts}[/]"
        lines.append(f"    {qa_info}")

    return lines
