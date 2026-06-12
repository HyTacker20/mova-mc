# AGENTS.md

AI agent reference for the MovaMC project.

## Project overview

A Python tool that translates Minecraft mod files between languages. It unpacks JAR files, finds language files (JSON/LANG/MCFUNCTION), translates their contents via Google Translate or AI providers (OpenAI, Anthropic, Gemini, Ollama, OpenAI-compatible), and repacks them into translated JARs.

Primary interfaces: **web UI** (`mova` → browser) and **CLI** (`mova cli`).

> **TUI deprecated:** `mova tui` / `src/app/interfaces/tui/` is **frozen** — no new features or UX fixes.
> All UI work goes to `frontend/` + `backend/`. The Textual TUI will be **removed** in a future release.
> See [`src/app/interfaces/tui/DEPRECATED.md`](src/app/interfaces/tui/DEPRECATED.md).

## Architecture

The project follows a **hexagonal (ports & adapters)** architecture with strict layer isolation enforced by `import-linter`:

```
src/app/
  __init__.py          Package init
  __main__.py          python -m app entry point
  __version__.py       VERSION tuple
  exceptions.py        Custom exception hierarchy
  logging_config.py    Loguru-based rotating file + console logger

  domain/              PURE domain models — zero I/O, zero external imports
    __init__.py        Re-exports models and stats
    models.py          TranslationUnit, TranslationResult, LangFile, Mod (all frozen dataclasses)
    languages.py       Language code registry, naming helpers, single-source from data/languages.json
    placeholders.py    %s/%d/%1$s positional and §-code extraction + multiset validation
    lint.py            Soft QA checks (e.g. lint_ukrainian for russisms detection)
    stats.py           FileStats, ModStats, OverallStats dataclasses

  application/         Pipeline orchestration — depends on domain, uses infrastructure ports
    pipeline.py        PipelineContext, build_context(), run_pipeline()
    ports.py           TranslationProvider, TranslationCache, ProgressSink protocols
    batching.py        chunk_list(), parse_chunk_response(), filter_empty()
    stages/
      unpack.py        JAR extraction via jar_unpacker
      discover.py      Find source language files + optional hint-language file
      parse.py         Read source files → TranslationUnit objects with placeholders + hint_text
      translate.py     Batch translation via CachingProvider-wrapped provider
      qa_refine.py     LLM judge batch QA + re-translation of flagged entries
      validate.py      Placeholder integrity check + soft QA lint (non-blocking)
      write.py         Write translated files to disk
      repack.py        JAR repacking via jar_packager (respects output_mode)

  infrastructure/      Concrete implementations — I/O, API calls, persistence
    providers/
      google.py               Google Translate via deep-translator
      openai_like.py           Unified LLM provider (OpenAI, LiteLLM, compatible APIs)
      caching.py               CachingProvider wrapper (SQLite-backed, version-aware cache key)
      prompts.py               System prompt templates with language-specific instructions
      glossary.py              Glossary loader for Minecraft terminology injection
      registry.py              check_provider_available() for all providers
      factory.py               get_translator_service() — provider instantiation
      helpers.py               Shared utilities (capitalize_first)
      transports/
        openai_sdk.py          OpenAI Python SDK transport
        litellm_sdk.py         LiteLLM transport
        compat_sdk.py          OpenAI-compatible API transport
    cache/
      sqlite_cache.py          SQLite-backed TranslationCache
    parsers/
      json_parser.py           JSON with comments (//, /* */)
      lang_parser.py           Minecraft LANG key=value format
      mcfunction_parser.py     data modify storage patterns
    filesystem/
      jar_unpacker.py          JAR → temp directory extraction
      jar_packager.py          Temp directory → JAR repacking

  interfaces/          User-facing interfaces (CLI and TUI)
    cli/
      args.py          ArgumentParser with subcommands (cli/app/init) and all flags
      main.py          CLI dispatcher: mova cli / app / init
      presenter.py     CLI stats/summary output
    tui/
      app.py           TranslationApp(App) — root Textual app, global bindings
      main.py          TUI entry: main(debug=False) → TranslationApp
      wizard.py        WizardScreen — stepper navigation, pipeline orchestration
      theme.py         Custom amber "dashboard" Textual theme
      key_bindings.py  Layout-independent Cyrillic keyboard aliases
      app.tcss         Global Textual CSS (centered column, amber focus)
      log_viewer.py    Modal log tail viewer
      translations_viewer.py  Modal source→target translation viewer
      steps/
        welcome.py     Step 0 — version, config indicator, start button
        provider.py    Step 1 — provider selection, credentials, model fetch
        paths.py       Step 2 — mods path, languages, output path
        advanced.py    Step 3 — cache, workers, hint lang, dry-run, glossary, QA
        mods.py        Step 4 — mod selection (SelectionList)
        translate_run.py  Step 5 — live progress bars + dual RichLog panels
        summary.py     Step 6 — results DataTable, restart/quit actions

  core/                Shared configuration and discovery
    settings.py        Settings class (CLI args + config file; flags: no_cache, hint_lang, output_mode)
    config_loader.py   movamc.toml loading and generation
    mod_scanner.py     JAR discovery and metadata scanning

  data/
    __init__.py        load_languages() — reads languages.json
    languages.json     Canonical language list (single source of truth)
    glossary/          Per-language glossary files (e.g. uk_UA.json)

  utils/
    retry_logic.py     Exponential backoff, RateLimitTracker, global_rate_limiter
    progress.py        ProgressReporter — pub/sub events for UI updates
```

## Translation flow

```
User input (CLI args or TUI form)
  → Settings object (resolves language codes, provider, flags)
  → pipeline.build_context(settings, progress) — resolves provider,
    wraps in CachingProvider with version-aware cache key
  → run_pipeline() stages:
      1. unpack    — JAR → temp/{mod_name}/
      2. discover  — find {source_lang}.json/.lang files + optional hint file
      3. parse     — read files → TranslationUnit[] with placeholders + hint_text
      4. translate — batch translate via provider with progress reporting
      5. qa_refine — LLM judge review (skipped when inline streaming QA ran)
      6. validate  — placeholder integrity check + soft QA lint
      7. write     — write target language files to temp/ (skipped on dry_run)
      8. repack    — temp/ → output JAR (skipped on dry_run; output_mode controls path)
  → cleanup temp workspace (unique per-run via tempfile.mkdtemp)
  → display stats (CLI) or SummaryStep (TUI)
```

## Key modules

### `domain/languages.py`

Language registry. Loads from `data/languages.json` as single source of truth.

| Function | Description |
|---|---|
| `get_language_options()` | Returns list of {name, value} for UI dropdowns |
| `get_language_name(code)` | Human display name for a code (e.g. `"en_US"` → `"English United States (en_US)"`) |
| `is_valid_language(code)` | True if code is in registry |
| `get_language_english_name(code)` | Human-readable English name without code suffix (e.g. `"uk_UA"` → `"Ukrainian"`) |

### `domain/placeholders.py`

Placeholder extraction and validation. Supports `%s`, `%d`, `%1$s` (positional), `§c` colour codes, `{name}`, and `{{placeholder}}`.

- `extract_placeholders(text)` — deduplicated tuple of found tokens
- `_count_placeholders(text)` — dict of token→count (for multiset validation)
- `validate_placeholders(original, translated)` — True if all original placeholders appear in translated with ≥ same count

### `domain/lint.py`

Soft QA checks for translation quality. Currently provides `lint_ukrainian(text)` which detects:
- Russian-only letters (ё, ъ, ы, э)
- Untranslated Latin word remnants

### `infrastructure/providers/prompts.py`

System prompt templates. Key features:
- `PROMPT_VERSION` constant — bumped when prompts change; included in cache key
- `LANG_SPECIFIC_INSTRUCTIONS` — per-target-language instructions (e.g. anti-surzhyk for Ukrainian)
- Glossary injection via `glossary_terms` parameter

### `infrastructure/providers/caching.py`

`CachingProvider` wraps any `TranslationProvider`. Cache key includes:
- Source text + source/target language
- Provider name + model
- `PROMPT_VERSION`
- Glossary signature (hash of glossary entries)

Supports `no_cache=True` to bypass cache entirely.

### `infrastructure/providers/openai_like.py`

Unified LLM provider. Accepts `source_lang_display` / `target_lang_display` for human-readable prompt names. Glossary loaded per-target-language.

### `infrastructure/providers/google.py`

Google Translate via `deep-translator`. Uses `capitalize_first()` from `helpers.py` instead of `str.capitalize()` to preserve non-initial letter casing.

### `infrastructure/providers/glossary.py`

Loads Minecraft terminology from `data/glossary/{lang_code}.json`. `get_relevant_terms()` finds which English terms appear in source texts and formats a prompt snippet. Supports user-defined glossary override via `set_user_glossary_path()`.

### `core/settings.py`

`Settings` holds all runtime configuration. Accepts `argparse.Namespace` and/or `config_data` dict.

| Property | CLI flag | Default |
|---|---|---|
| `source_mc_lang` | `--source -s` | `en_US` |
| `target_mc_lang` | `--target -t` | `es_ES` |
| `mods_path` | `--path -p` | `./` |
| `translation_path` | `--output -o` | `./translated_mods` |
| `provider` | `--provider` | `google` |
| `max_workers` | `--workers` | `4` |
| `dry_run` | `--dry-run` | `False` |
| `no_cache` | `--no-cache` | `False` |
| `hint_lang` | `--hint-lang` | `None` |
| `glossary_path` | `--glossary-path` | `None` |
| `output_mode` | `--output-mode` | `"separate"` |
| `qa_judge` | TUI / config | `False` |

`Settings.effective_output_path()` returns `mods_path` when `output_mode == "replace"`,
otherwise `translation_path`.

### `infrastructure/providers/factory.py`

Single function `get_translator_service()` resolves the correct provider. For LLM providers it accepts `source_lang_display` / `target_lang_display` for human-readable prompt names. Google always receives ISO codes.

### `interfaces/tui/` (Textual) — **deprecated, do not extend**

Legacy terminal UI. **Do not implement new features here** — use the web UI instead.
Kept only until removal. Entry point: `main.py:main(debug=False)`.

| File | Purpose |
|---|---|
| `app.py` | `TranslationApp(App)` — pushes WizardScreen, global quit bindings |
| `main.py` | Entry point preserving `main(debug=False)` signature |
| `wizard.py` | `WizardScreen` — stepper, navigation, pipeline worker, clipboard |
| `steps/welcome.py` | Welcome step with config indicator and start button |
| `steps/provider.py` | Provider/credentials/model selection with auto-save |
| `steps/paths.py` | Mods path, source/target languages, output path |
| `steps/advanced.py` | Cache, workers, hint lang, dry-run, glossary, QA settings |
| `steps/mods.py` | Mod selection via SelectionList |
| `steps/translate_run.py` | Live progress + Translation/QA log panels |
| `steps/summary.py` | Results DataTable, view log/translations, restart |
| `app.tcss` | Global Textual CSS (amber dashboard theme) |

Flow: Welcome → Provider → Paths → Advanced → Mods → Translate → Summary.
Back from Summary returns to Mods. "New Translation" restarts at Welcome.

### Persistable config keys (movamc.toml)
| Key | Type | Section |
|---|---|---|
| `source` | string | `[translation]` |
| `target` | string | `[translation]` |
| `provider` | string | `[translation]` |
| `workers` | integer | `[translation]` |
| `output` | string | `[translation]` |
| `no_cache` | bool | `[translation]` |
| `hint_lang` | string | `[translation]` |
| `glossary_path` | string | `[translation]` |
| `output_mode` | string | `[translation]` |
| `include` | list of strings | `[mods]` |
| `exclude` | list of strings | `[mods]` |

## Conventions

### Logging
```python
from loguru import logger
```
Use loguru directly, never `print()`. Log levels: INFO for progress, WARNING for retries/fallback, ERROR for failures, DEBUG for verbose API responses.

### Type hints
All public methods use full type annotations (`dict[str, str]`, `list[str]`, `Path`, `bool`, `int`). Use `X | None` for optionals. Use `collections.abc.Callable` for callables.

### Imports
- Ruff sorts imports (I rule) — standard library first, then third-party, then relative
- Use relative imports within the package: `from ..core.settings import Settings`

### Layer rules (enforced by import-linter)
- **domain** must NOT import infrastructure or application
- **application** must NOT import interfaces
- Data/resource packages (`data/`) are not infrastructure — importing from them is allowed

### Error handling
Translation failures are logged and fall back to returning original text. Don't let a single translation failure stop the entire batch. QA lint warnings are non-blocking.

## Project commands

```bash
uv sync                    # Install all deps
uv run pytest              # Run tests
uv run pytest --cov        # Run tests with coverage
uv run ruff check .        # Lint
uv run ruff format .       # Format
uv run mypy src/           # Type check
uv run lint-imports        # Check layer isolation
uv run mova tui  # Run interactive TUI
uv run mova cli  # Run CLI
```

## Environment variables

Copy `.env.example` to `.env`. Supported vars:

| Variable | Provider | Required |
|---|---|---|
| `TRANSLATION_MODEL` | All AI | No (default: gpt-4o-mini) |
| `OPENAI_API_KEY` | openai | Yes |
| `OPENAI_MODEL` | openai | No (default: gpt-4o-mini) |
| `ANTHROPIC_API_KEY` | anthropic | Yes |
| `GEMINI_API_KEY` | gemini | Yes |
| `OLLAMA_API_BASE` | ollama | No (default: http://localhost:11434) |
| `OPENAICOMPATIBLE_API_KEY` | openaicompatible | Yes |
| `OPENAICOMPATIBLE_BASE_URL` | openaicompatible | Yes |
| `OPENAICOMPATIBLE_MODEL` | openaicompatible | No |

## Test structure

```
tests/
  conftest.py                      Shared fixtures (sample JSON/LANG/mcfunction, temp dirs, JAR builder)
  contracts/
    test_provider_contract.py      Provider interface contract tests
  integration/
    test_jar_roundtrip.py          Full JAR roundtrip integration
    test_pipeline_e2e.py           End-to-end pipeline test
  test_app.py                      Interactive app tests
  test_tui_smoke.py                Textual wizard smoke tests
  test_key_bindings.py             Cyrillic keyboard layout bindings
  test_command_line_extended.py    CLI arg parsing
  test_config_loader.py            Config file loading
  test_data.py                     languages.json loading
  test_file_manager.py             Legacy file manager tests
  test_file_manager_extended.py    Legacy edge cases
  test_google_translate_service.py Google service tests
  test_json_parser_edge.py         JSON parser edge cases
  test_lang_parser_edge.py         LANG parser edge cases
  test_logging_config.py           Logger setup
  test_main_entry.py               __main__.py entry point
  test_mcfunction_parser_edge.py   MCFUNCTION parser edge cases
  test_mod_scanner.py              Mod scanner tests
  test_openai_check.py             Provider check logic
  test_openai_compatible_service.py OpenAI-compatible service tests
  test_openai_translate_service.py  OpenAI service tests
  test_progress_extended.py        ProgressReporter tests
  test_retry_logic.py              Retry/backoff tests
  test_settings.py                 Settings tests
  test_settings_extended.py        Settings edge cases
  test_stats.py                    Stats dataclass tests
  test_translate_orchestrator.py   Translate command orchestration
  test_translator.py               Translator wrapper
  test_version.py                  Version tuple
```

## File format support

| Format | Extension | Structure | Parser |
|---|---|---|---|
| JSON with comments | `.json` | `{"key": "value"}` with `//` and `/* */` comments | `infrastructure/parsers/json_parser.py` |
| Minecraft LANG | `.lang` | `key=value` per line | `infrastructure/parsers/lang_parser.py` |
| MCFUNCTION | `.mcfunction` | Lines with `data modify storage ... set value "..."` | `infrastructure/parsers/mcfunction_parser.py` |

Source files are detected by filename: `{lang_code}.json` or `{lang_code}.lang` (case-insensitive). Target files are written with casing detected from existing files in the same directory.
