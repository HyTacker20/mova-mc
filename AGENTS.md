# AGENTS.md

AI agent reference for the MovaMC project.

## Project overview

A Python tool that translates Minecraft mod files between languages. It unpacks JAR files, finds language files (JSON/LANG/MCFUNCTION), translates their contents via Google Translate or AI providers (OpenAI, Anthropic, Gemini, Ollama, OpenAI-compatible), and repacks them into translated JARs.

Primary interfaces: **web UI** (`mova` → browser) and **CLI** (`mova cli`).

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
      qa_wrapper.py            InlineQaWrapper — LLM judge + re-translation decorator
      judge.py                 LLM judge client (binary verdict: ok/flag)
      judge_prompts.py         Judge system prompt templates (v1.5 binary prompt)
      reasoning_models.py      Centralized reasoning model policy + token scaling
      model_list.py            Live model list fetching per provider
      transports/
        openai_sdk.py          OpenAI Python SDK transport
        litellm_sdk.py         LiteLLM transport
        compat_sdk.py          OpenAI-compatible API transport
        opencode.py            OpenCode Go transport (facade over compat/anthropic)
        anthropic_compat.py    Anthropic Messages API transport
      factory.py               get_translator_service() — provider instantiation
      registry.py              Provider registration + model resolution
      helpers.py               Shared utilities (capitalize_first)
    cache/
      sqlite_cache.py          SQLite-backed TranslationCache
    parsers/
      json_parser.py           JSON with comments (//, /* */)
      lang_parser.py           Minecraft LANG key=value format
      mcfunction_parser.py     data modify storage patterns
    filesystem/
      jar_unpacker.py          JAR → temp directory extraction
      jar_packager.py          Temp directory → JAR repacking

  interfaces/          User-facing interfaces (CLI)
    cli/
      args.py          ArgumentParser with subcommands (cli/init/web) and all flags
      main.py          CLI dispatcher: mova cli / init / web
      presenter.py     CLI stats/summary output

frontend/             React + TypeScript web UI (Vite)
  src/
    components/
      Wizard.tsx         Main wizard stepper (7 steps)
      steps/
        Welcome.tsx      Step 0 — version, config indicator
        Provider.tsx     Step 1 — provider, API key, model
        Paths.tsx        Step 2 — mods path, languages, output
        Advanced.tsx     Step 3 — QA settings, cache, glossary
        Mods.tsx         Step 4 — mod selection
        Translate.tsx    Step 5 — job configuration
        TranslationRun.tsx  Step 6 — live progress + QA panels
        Summary.tsx      Step 7 — results, restart
      shared/
        LogPanel.tsx     Real-time SSE log viewer (All/Translation/QA tabs)
        LiveResultsPanels.tsx  Live translation + QA cards
        ModList.tsx      Mod selection list
    context/
      WizardContext.tsx  Global wizard state + reducer
    utils/
      qaLive.ts         QA event → card mapping + dedup logic
      errors.ts         User-friendly error messages (Ukrainian)

backend/              FastAPI backend
    main.py              uvicorn entry point, lifespan, CORS
    routes/
      config.py          Config read/write API
      jobs.py            Job lifecycle (start/pause/resume/cancel)
      logs.py            SSE loguru sink → LogPanel
      mods.py            Mod scanning API
      translate.py       Translation pipeline orchestration
    dev_progress_log.py  ProgressReporter → loguru relay
    job_manager.py       TranslationJob lifecycle

  core/                Shared configuration and discovery
    settings.py        Settings class (CLI args + config file; delegates to PathConfig/QaConfig)
    config_loader.py   movamc.toml loading and generation
    mod_scanner.py     JAR discovery and metadata scanning
    path_config.py     PathConfig dataclass (mods_path, translation_path, output_mode)
    qa_config.py       QaConfig dataclass (judge settings, model resolution, validation)
    dotenv_loader.py   .env file loading

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
User input (CLI args or web form)
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
  → display stats (CLI or web UI)
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
| `qa_judge` | config | `False` |

`Settings.effective_output_path()` returns `mods_path` when `output_mode == "replace"`,
otherwise `translation_path`.

### `infrastructure/providers/factory.py`

Single function `get_translator_service()` resolves the correct provider. For LLM providers it accepts `source_lang_display` / `target_lang_display` for human-readable prompt names. Google always receives ISO codes.

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
uv run mova web           # Launch web UI (primary)
uv run mova cli           # Run CLI
cd frontend && npm run build  # Build frontend (TypeScript + Vite)
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
| `OPENCODE_GO_API_KEY` | opencode | Yes |
| `OPENCODE_GO_BASE_URL` | opencode | No (default: https://opencode.ai/zen/go/v1) |
| `OPENCODE_GO_MODEL` | opencode | No (default: deepseek-v4-flash) |

## Test structure

```
tests/
  conftest.py                      Shared fixtures (sample JSON/LANG/mcfunction, temp dirs, JAR builder)
  contracts/
    test_provider_contract.py      Provider interface contract tests
    test_reasoning_transport.py    Reasoning transport contract tests
  integration/
    test_jar_roundtrip.py          Full JAR roundtrip integration
    test_pipeline_e2e.py           End-to-end pipeline test
    test_e2e_extended.py           Extended E2E tests
  test_app.py                      Interactive app tests
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

  # Web UI / backend
  test_web_api.py                  FastAPI endpoint tests
  test_web_logging.py              SSE log streaming tests
  test_job_bridge.py               TranslationJob bridge tests

  # QA / Judge
  test_judge.py                    LLM judge client tests
  test_judge_prompts.py            Judge prompt template tests
  test_inline_qa_wrapper.py        InlineQaWrapper decorator tests
  test_qa_display.py               QA display formatting tests

  # Pipeline stages
  test_stages.py                   Individual pipeline stage tests
  test_validate.py                 Placeholder validation tests
  test_lint_ukrainian.py           Ukrainian-specific lint rules

  # Providers
  test_opencode_provider.py        OpenCode Go transport tests
  test_openai_batch.py             OpenAI batch translation tests
  test_transport_response.py       Transport response handling tests
  test_reasoning_models.py         Reasoning model policy tests
  test_caching.py                  SQLite cache tests

  # Config / settings
  test_config_roundtrip.py         Config file roundtrip tests
  test_performance_settings.py     Chunk/worker/batch settings tests
  test_token_budget.py             Token budget calculation tests
  test_domain_property.py          Domain model property tests

  # Infrastructure
  test_glossary.py                 Glossary loader tests
  test_archive_handler.py          Archive handler tests
  test_jar_packager.py             JAR packager tests
  test_shutdown.py                 Graceful shutdown tests
  test_presenter.py                CLI presenter tests
  test_translate_run_progress.py   Progress reporting tests
  test_languages_extended.py       Extended language registry tests
  test_placeholders_extended.py    Extended placeholder tests
```

## File format support

| Format | Extension | Structure | Parser |
|---|---|---|---|
| JSON with comments | `.json` | `{"key": "value"}` with `//` and `/* */` comments | `infrastructure/parsers/json_parser.py` |
| Minecraft LANG | `.lang` | `key=value` per line | `infrastructure/parsers/lang_parser.py` |
| MCFUNCTION | `.mcfunction` | Lines with `data modify storage ... set value "..."` | `infrastructure/parsers/mcfunction_parser.py` |

Source files are detected by filename: `{lang_code}.json` or `{lang_code}.lang` (case-insensitive). Target files are written with casing detected from existing files in the same directory.
