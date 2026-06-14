import shutil
import sys

from loguru import logger

from ...application.pipeline import build_context, run_pipeline
from ...core.config_loader import find_config_file, load_config
from ...core.mod_scanner import ModScanner, modinfo_to_domain_mod
from ...core.settings import Settings
from ...infrastructure.providers.registry import check_provider_available
from ...logging_config import is_logging_configured, setup_logging
from ...utils.cancellation import cancel_token
from ...utils.progress import ProgressReporter
from .args import build_argument_parser
from .presenter import export_stats_json, print_cli_summary

JAR = ".jar"


_KNOWN_COMMANDS = frozenset({"cli", "init", "web"})
_HELP_FLAGS = frozenset({"-h", "--help"})


def main() -> None:
    try:
        # Default to web UI when no subcommand is given
        if len(sys.argv) == 1 or (
            len(sys.argv) > 1 and sys.argv[1] not in _KNOWN_COMMANDS and sys.argv[1] not in _HELP_FLAGS
        ):
            sys.argv.insert(1, "web")

        parser = build_argument_parser()
        args = parser.parse_args()

        if getattr(args, "command", None) == "init":
            from ...core.config_loader import generate_config_template

            path = generate_config_template(args.directory)
            logger.info(f"Config template created at: {path}")
            return

        if getattr(args, "command", None) == "web":
            from backend.__main__ import main as web_main

            web_main(
                host=getattr(args, "host", None),
                port=getattr(args, "port", None),
                dev=getattr(args, "dev", None),
                debug=getattr(args, "debug", None),
                no_browser=getattr(args, "no_browser", None),
            )
        else:
            _run_translation(args)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception:
        logger.exception("Error")
        sys.exit(1)


def _resolve_provider(args) -> str:
    return getattr(args, "provider", "google")


def _run_translation(args) -> None:
    provider = _resolve_provider(args)

    ok, message = check_provider_available(provider)
    if not ok:
        logger.error(message)
        return
    logger.info(message)

    if not is_logging_configured():
        debug = getattr(args, "debug", False)
        json_log = getattr(args, "log_format", "text") == "json"
        setup_logging(console_level="DEBUG" if debug else "INFO", json_format=json_log)

    args.provider = provider

    config_data = None
    config_path = find_config_file(getattr(args, "path", "./"), getattr(args, "config", None))
    if config_path:
        config_data = load_config(config_path)

    settings = Settings(cli_args=args, config_data=config_data)
    settings.debug = getattr(args, "debug", False)

    scanner = ModScanner(settings.mods_path, source_lang=settings.source_mc_lang)
    reporter = ProgressReporter()
    scanner.reporter = reporter

    mod_infos = scanner.discover_mods(include=settings.include_mods, exclude=settings.exclude_mods)

    if settings.selected_mods:
        selected_set = set(settings.selected_mods)
        for mod in mod_infos:
            mod.selected = mod.name in selected_set

    selected_count = sum(1 for m in mod_infos if m.selected)
    has_explicit_filter = bool(settings.selected_mods or settings.include_mods or settings.exclude_mods)

    if getattr(args, "dry_run", False):
        _print_dry_run(settings, mod_infos, selected_count)
        return

    if selected_count == 0 and has_explicit_filter:
        logger.warning("No mods matched the selection criteria. Exiting.")
        return

    total_estimated = sum(m.estimated_entries for m in mod_infos if m.selected)
    logger.info(f"Selected {selected_count} / {len(mod_infos)} mods (~{total_estimated} estimated entries)")

    mods = [modinfo_to_domain_mod(m) for m in mod_infos if m.selected]

    cancel_token.clear()
    ctx = build_context(settings, reporter, model=settings.model)

    try:
        result = run_pipeline(ctx, mods)
    except KeyboardInterrupt:
        cancel_token.set()
        logger.info("Translation cancelled by user")
        return
    finally:
        if ctx.workspace.exists():
            shutil.rmtree(str(ctx.workspace), ignore_errors=True)

    export_path = getattr(args, "export_stats", None)
    if export_path:
        export_stats_json(result.stats, export_path)

    print_cli_summary(result.stats)


def _print_dry_run(settings: Settings, mods: list, selected_count: int) -> None:
    logger.info("--- DRY RUN ---")
    logger.info(f"Mods path: {settings.mods_path}")
    logger.info(f"Source language: {settings.source_mc_lang}")
    logger.info(f"Target language: {settings.target_mc_lang}")
    logger.info(f"Translation provider: {settings.provider}")
    logger.info(f"Output path: {settings.translation_path}")
    logger.info(f"Workers: {settings.max_workers}")
    logger.info(f"Found {len(mods)} JAR(s): {selected_count} selected")

    if selected_count == 0:
        logger.info("No mods to translate in dry run.")
        logger.info("--- DRY RUN COMPLETE (no files modified) ---")
        return

    logger.info(f"Would translate the following {selected_count} mod(s):")
    for mod in mods:
        if mod.selected:
            for f in mod.source_files:
                logger.info(f"  - {mod.name} -> {f}")
    logger.info("--- DRY RUN COMPLETE (no files modified) ---")


if __name__ == "__main__":
    main()
