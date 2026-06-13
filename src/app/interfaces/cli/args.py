from argparse import ArgumentParser


def add_translate_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("-p", "--path", help="Path to mod or mod folder", default="./mods")
    parser.add_argument("-s", "--source", help="Source language code (e.g., en_US)")
    parser.add_argument("-t", "--target", help="Target language code (e.g., es_ES)")
    parser.add_argument("-o", "--output", help="Output folder path")
    parser.add_argument(
        "--provider",
        type=str,
        default="google",
        choices=["google", "openai", "anthropic", "gemini", "ollama", "litellm", "openaicompatible", "opencode"],
        help="Translation provider (default: google)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name for AI providers (e.g. gpt-4o, claude-sonnet-4). Uses provider default if not set.",
    )
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent translation workers (default: 4)")
    parser.add_argument(
        "--chunk-mode",
        type=str,
        default=None,
        choices=["auto", "chunk", "item"],
        help="Translation batching: auto (token budget), chunk (fixed size), item (one per request)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Fixed chunk size when --chunk-mode=chunk (default: provider default, usually 25)",
    )
    parser.add_argument(
        "--chunk-token-budget",
        type=int,
        default=None,
        help="Max estimated input tokens per JSON batch when --chunk-mode=auto (default: 3500)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be translated without making changes")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging to console")
    parser.add_argument(
        "--log-format",
        type=str,
        default="text",
        choices=["text", "json"],
        help="Log file format (default: text)",
    )
    parser.add_argument(
        "--include-mods",
        type=str,
        default=None,
        help="Comma-separated glob patterns for mods to include (e.g. '*Iron*,*JEI*')",
    )
    parser.add_argument(
        "--exclude-mods",
        type=str,
        default=None,
        help="Comma-separated glob patterns for mods to exclude (e.g. 'test_*,debug_*')",
    )
    parser.add_argument(
        "--mods-list",
        type=str,
        default=None,
        help="Path to a text file listing mod names to translate (one per line)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore translation cache and retranslate everything",
    )
    parser.add_argument(
        "--hint-lang",
        type=str,
        default=None,
        help="Hint/reference language code (e.g. ru_RU) for LLM bilingual context (ignored by Google)",
    )
    parser.add_argument(
        "--glossary-path",
        type=str,
        default=None,
        help="Path to a custom glossary JSON file for terminology control",
    )
    parser.add_argument(
        "--output-mode",
        type=str,
        default=None,
        choices=["replace", "separate"],
        help="Output mode: 'replace' overwrites original mod JARs (DANGEROUS), "
        "'separate' writes translated JARs to the --output folder (default: separate)",
    )
    parser.add_argument(
        "--export-stats",
        type=str,
        default=None,
        help="Export translation statistics as JSON to the given path",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to movamc.toml config file (auto-discovered if not specified)",
    )
    parser.add_argument(
        "--qa-judge",
        action="store_true",
        help="Enable LLM-as-judge QA pass over translated entries",
    )
    parser.add_argument(
        "--qa-judge-provider",
        type=str,
        default=None,
        help="Provider for the QA judge (default: main translation provider)",
    )
    parser.add_argument(
        "--qa-judge-model",
        type=str,
        default=None,
        help="Model for the QA judge (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--qa-corrector-model",
        type=str,
        default=None,
        help="Model for re-translating flagged entries (default: main translation model)",
    )
    parser.add_argument(
        "--qa-threshold",
        type=int,
        default=None,
        help="Flag for re-translation when score <= this (default: 3)",
    )
    parser.add_argument(
        "--qa-max-attempts",
        type=int,
        default=None,
        help="Max re-translation attempts per flagged entry (default: 2)",
    )


def build_argument_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="mova")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    cli_parser = subparsers.add_parser("cli", help="Use traditional command-line arguments")
    add_translate_arguments(cli_parser)

    app_parser = subparsers.add_parser("tui", help="Launch interactive Textual TUI")
    app_parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging to console")

    init_parser = subparsers.add_parser("init", help="Generate a movamc.toml config template")
    init_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to create movamc.toml in (default: current directory)",
    )

    web_parser = subparsers.add_parser("web", help="Launch browser-based web UI")
    web_parser.add_argument("--host", default=None, help="Bind host (env: MOVAMC_HOST)")
    web_parser.add_argument("--port", type=int, default=None, help="Listen port (env: MOVAMC_PORT)")
    web_parser.add_argument(
        "--dev", action="store_const", const=True, default=None, help="Dev mode + CORS (env: MOVAMC_DEV)"
    )
    web_parser.add_argument(
        "-d", "--debug", action="store_const", const=True, default=None, help="Debug logging (env: MOVAMC_DEBUG)"
    )
    web_parser.add_argument(
        "--no-browser", action="store_const", const=True, default=None, help="Skip browser (env: MOVAMC_NO_BROWSER)"
    )

    return parser
