<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--NC%204.0-blue.svg" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python"></a>
</p>

# MovaMC

A tool for translating Minecraft mods into multiple languages, automating the localization process for mod developers and translators.

> **Note:** The terminal TUI (`mova tui`) is **deprecated** and will be removed. Use the **web UI** (`mova`) or **CLI** (`mova cli`) instead.

## Features

- **Automated Translation** — Translate mod JARs via web UI or CLI
- **AI-Powered Translation** — OpenAI, Anthropic, Gemini, Ollama, OpenCode Go, OpenAI-Compatible
- **JAR Pipeline** — Extract, translate LANG/JSON/MCFUNCTION assets, and repack mods
- **Multiple Translation Services** — Google Translate (free) or AI providers with SQLite translation cache
- **Batch Processing** — Translate single files, entire mod folders, or batch-select mods in the web UI
- **uk_UA QA** — Optional inline LLM judge with tiered fix acceptance for Ukrainian targets

## Translation Providers

| Provider | Flag | Cost | Requirements |
|---|---|---|---|
| Google Translate | `--provider google` | Free | `deep-translator` package |
| OpenAI | `--provider openai` | Paid | `OPENAI_API_KEY` |
| Anthropic Claude | `--provider anthropic` | Paid | `ANTHROPIC_API_KEY` |
| Google Gemini | `--provider gemini` | Paid/Free tier | `GEMINI_API_KEY` |
| Ollama (Local) | `--provider ollama` | Free | Ollama running locally |
| OpenCode Go | `--provider opencode` | Paid ($5–10/mo) | `OPENCODE_GO_API_KEY` |
| OpenAI-Compatible | `--provider openaicompatible` | Varies | `OPENAICOMPATIBLE_API_KEY` + `OPENAICOMPATIBLE_BASE_URL` |

## Installation

### Pre-built Executables

Download ready-to-use executable files from the releases page:

- **App Version** — `MovaMC.exe` (interactive application)
- **CLI Version** — `mova.exe` (command-line interface)

No Python installation required.

### From Source

```bash
# Install uv first (https://docs.astral.sh/uv/getting-started/installation/)
git clone git@github.com:HyTacker20/mova-mc.git
cd mova-mc

# Setup the environment (Windows)
scripts\setup.bat
# Or for Linux/Mac
./scripts/setup.sh

# Install dependencies
uv sync

# Run the application (Windows)
scripts\start.bat
# Or for Linux/Mac
./scripts/start.sh
```

## Configuration

Copy `.env.example` to `.env` and configure your API keys:

```bash
cp .env.example .env
```

Supported environment variables:

| Variable | Provider | Required | Default |
|---|---|---|---|
| `TRANSLATION_MODEL` | All AI | No | `gpt-4o-mini` |
| `OPENAI_API_KEY` | openai | Yes | — |
| `OPENAI_MODEL` | openai | No | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | anthropic | Yes | — |
| `GEMINI_API_KEY` | gemini | Yes | — |
| `OLLAMA_API_BASE` | ollama | No | `http://localhost:11434` |
| `OPENAICOMPATIBLE_API_KEY` | openaicompatible | Yes | — |
| `OPENAICOMPATIBLE_BASE_URL` | openaicompatible | Yes | — |
| `OPENAICOMPATIBLE_MODEL` | openaicompatible | No | `gpt-4o-mini` |
| `OPENCODE_GO_API_KEY` | opencode | Yes | — |
| `OPENCODE_GO_MODEL` | opencode | No | `deepseek-v4-flash` |
| `OPENCODE_GO_BASE_URL` | opencode | No | `https://opencode.ai/zen/go/v1` |

## Usage

### Web UI (recommended)

```bash
mova
```

Opens the browser-based wizard at `http://127.0.0.1:8000` (translation settings, mod selection, live progress, QA panel).

### Command Line Interface

```bash
# Basic usage with Google Translate (free)
mova cli --path path/to/mods --source en_US --target es_ES --output path/to/output

# AI-powered translation with OpenAI (requires API key)
mova cli --path path/to/mods --source en_US --target es_ES --output path/to/output --provider openai

# Use Anthropic Claude
mova cli --path path/to/mods --source en_US --target es_ES --output path/to/output --provider anthropic

# Use Google Gemini
mova cli --path path/to/mods --source en_US --target es_ES --output path/to/output --provider gemini

# Use local Ollama
mova cli --path path/to/mods --source en_US --target es_ES --output path/to/output --provider ollama

# Dry-run to preview changes
mova cli --path path/to/mods --source en_US --target es_ES --dry-run

# Parameters:
# --path (-p): Path to mod or mods folder (default: ./mods)
# --source (-s): Source language code (e.g., en_US)
# --target (-t): Target language code (e.g., es_ES)
# --output (-o): Output folder path (if same as mods path, will replace original mods)
# --provider: Translation provider (google, openai, anthropic, gemini, ollama, openaicompatible, opencode)
# --workers: Number of concurrent translation workers (default: 4)
# --dry-run: Show what would be translated without making changes
# --debug (-d): Enable debug logging
```

> The `--ai` flag is deprecated. Use `--provider openai` instead.

## Development

### Setup

```bash
uv sync                # Install all dependencies
uv sync --group dev    # Install dev tools (pytest, ruff, mypy)
```

### Commands

```bash
uv run pytest              # Run tests
uv run pytest --cov        # Run tests with coverage
uv run ruff check .        # Lint
uv run ruff format .       # Format
uv run mypy src/           # Type check
```

### Project Structure

```
src/app/
  domain/          Pure data models, language registry, placeholder validation
  application/     Pipeline orchestration (unpack → discover → parse → translate → validate → write → repack)
  infrastructure/  Providers (Google, OpenAI, LiteLLM, etc.), parsers, cache, filesystem I/O
  interfaces/      CLI (argparse) and TUI (Textual framework)
  core/            Settings, config loader, mod scanner
  services/        Provider factory
  data/            Language list and glossary files
  utils/           Retry logic, rate limiting, progress reporting
tests/             Pytest test suite (contracts, integration, unit tests)
scripts/           Build and setup scripts
```

## License

This project is licensed under the [Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)](LICENSE).
