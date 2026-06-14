from __future__ import annotations

from loguru import logger

from ...domain.lint import lint_ukrainian
from ...domain.models import LangFile, Mod, TranslationResult
from ...domain.placeholders import validate_placeholders
from ...utils.cancellation import cancel_token
from ..pipeline import PipelineContext


def stage_validate_outputs(ctx: PipelineContext, mods: list[Mod]) -> list[Mod]:
    """Validate translated text preserves Minecraft formatting placeholders
    and run soft QA checks (language lint, suspicious patterns).

    Placeholder validation marks translations with missing placeholders as
    failed so they are not used.  QA checks are non-blocking warnings
    attached to the TranslationResult's ``qa_warnings`` field.
    """
    target_lang = ctx.settings.target_mc_lang
    run_uk_lint = target_lang == "uk_UA"

    result: list[Mod] = []
    for mod in mods:
        if not mod.selected:
            result.append(mod)
            continue

        cancel_token.raise_if_set()

        validated_files: list[LangFile] = []
        for lang_file in mod.lang_files:
            validated_units = tuple(
                _validate_result(u, ctx=ctx, run_uk_lint=run_uk_lint) if isinstance(u, TranslationResult) else u
                for u in lang_file.units
            )
            validated_files.append(
                LangFile(
                    mod_name=lang_file.mod_name,
                    source_path=lang_file.source_path,
                    target_path=lang_file.target_path,
                    file_type=lang_file.file_type,
                    units=validated_units,
                )
            )

        result.append(
            Mod(
                name=mod.name,
                path=mod.path,
                lang_files=tuple(validated_files),
                selected=mod.selected,
            )
        )

    return result


def _validate_result(
    result: TranslationResult,
    *,
    ctx: PipelineContext,
    run_uk_lint: bool = False,
) -> TranslationResult:
    # ── Placeholder validation (hard failure) ──
    if result.success:
        is_valid = validate_placeholders(result.unit.source_text, result.translated_text)
        if not is_valid:
            logger.debug(
                "Placeholder validation failed for '{}': source='{}', translated='{}'",
                result.unit.key,
                result.unit.source_text,
                result.translated_text,
            )
            return TranslationResult(
                unit=result.unit,
                translated_text=result.translated_text,
                success=False,
                error="Placeholder validation failed",
            )

    # ── Soft QA checks ──
    qa_warnings: tuple[dict, ...] = ()
    if run_uk_lint and result.translated_text:
        qa_warnings = tuple(lint_ukrainian(result.translated_text))

    if qa_warnings:
        logger.debug("QA warnings for '{}': {}", result.unit.key, qa_warnings)
        for warning in qa_warnings:
            msg = warning.get("message", warning.get("type", "warning"))
            ctx.progress.report_qa_warning(result.unit.key, str(msg))

    # Only create a new result if we have warnings (otherwise return unchanged)
    if qa_warnings:
        return TranslationResult(
            unit=result.unit,
            translated_text=result.translated_text,
            success=result.success,
            cached=result.cached,
            error=result.error,
            qa_warnings=qa_warnings,
            qa_score=result.qa_score,
            qa_issue=result.qa_issue,
            qa_attempts=result.qa_attempts,
        )

    return result
