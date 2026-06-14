from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]

import tomli_w

CONFIG_FILE_NAME = "movamc.toml"
HIDDEN_CONFIG_FILE_NAME = ".movamc.toml"

VALID_CONFIG_KEYS = frozenset(
    {
        "source",
        "target",
        "provider",
        "model",
        "workers",
        "output",
        "no_cache",
        "hint_lang",
        "glossary_path",
        "output_mode",
        "path",
        "chunk_mode",
        "chunk_size",
        "chunk_token_budget",
        "chunk_max_text_length",
        "progress_batch_size",
        "ui_locale",
    }
)
VALID_MOD_KEYS = frozenset({"include", "exclude"})
VALID_QA_KEYS = frozenset(
    {
        "judge",
        "judge_model",
        "judge_provider",
        "corrector_model",
        "threshold",
        "max_attempts",
        "chunk_size",
        "judge_workers",
    }
)
VALID_RATE_LIMIT_KEYS = frozenset({"rpm", "burst"})


def settings_to_config_dict(settings: Any, *, ui_locale: str | None = None) -> dict[str, Any]:
    """Build a flat config dict from :class:`Settings` for :func:`save_config`."""
    data: dict[str, Any] = {
        "source": settings.source_mc_lang,
        "target": settings.target_mc_lang,
        "provider": settings.provider,
        "model": settings.model,
        "workers": settings.max_workers,
        "translation_path": settings.translation_path,
        "mods_path": settings.mods_path,
        "hint_lang": settings.hint_lang,
        "glossary_path": settings.glossary_path,
        "no_cache": settings.no_cache,
        "output_mode": settings.output_mode,
        "chunk_mode": settings.chunk_mode,
        "chunk_size": settings.chunk_size,
        "chunk_token_budget": settings.chunk_token_budget,
        "chunk_max_text_length": settings.chunk_max_text_length,
        "progress_batch_size": settings.progress_batch_size,
        "qa_judge": settings.qa_judge,
        "qa_judge_provider": settings.qa_judge_provider,
        "qa_judge_model": settings.qa_judge_model,
        "qa_corrector_model": settings.qa_corrector_model,
        "qa_threshold": settings.qa_threshold,
        "qa_max_attempts": settings.qa_max_attempts,
        "qa_chunk_size": settings.qa_chunk_size,
        "qa_judge_workers": settings.qa_judge_workers,
    }
    if ui_locale is not None:
        data["ui_locale"] = ui_locale
    rate_limit: dict[str, Any] = {}
    if settings.rate_limit_rpm is not None:
        rate_limit["rpm"] = settings.rate_limit_rpm
    if settings.rate_limit_burst is not None:
        rate_limit["burst"] = settings.rate_limit_burst
    for service, svc_cfg in settings.rate_limit_services.items():
        if isinstance(svc_cfg, dict) and svc_cfg:
            rate_limit[service] = dict(svc_cfg)
    if rate_limit:
        data["rate_limit"] = rate_limit
    return data


CONFIG_TEMPLATE = """# MovaMC configuration
# This file is auto-discovered when placed next to your mods.
# CLI arguments override values set here.

[translation]
# Source language code (e.g., en_US)
source = "en_US"

# Target language code (e.g., uk_UA)
target = "uk_UA"

# Translation provider: google, openai, anthropic, gemini, ollama, litellm, openaicompatible, opencode
provider = "google"

# Model name for AI providers (e.g. gpt-4o, claude-sonnet-4). Uses provider default if not set.
# model = ""

# Number of concurrent translation workers
workers = 4

# Output directory for translated mods (relative to config file or absolute)
# output = "./translated_mods"

# Disable translation cache (useful for re-translation)
# no_cache = false

# Path to a glossary file for terminology injection
# glossary_path = ""

# Hint language code to assist translation (e.g., "ru_RU" for uk_UA target)
# hint_lang = ""

# Output mode: "resourcepack" (build .zip pack), "separate" (keep both), or "replace" (overwrite originals)
# output_mode = "resourcepack"

[mods]
# Glob patterns for mods to include (default: all mods)
# include = ["*"]
# Glob patterns for mods to exclude
# exclude = ["test_*", "example_*"]
"""


def find_config_file(mods_path: str, explicit_path: str | None = None) -> Path | None:
    if explicit_path:
        explicit = Path(explicit_path)
        if explicit.is_file():
            logger.info(f"Using explicitly specified config file: {explicit}")
            return explicit
        logger.warning(f"Explicit config file not found: {explicit}")
        return None

    search_paths: list[Path] = []

    mods_dir = Path(mods_path).resolve()
    if mods_dir.is_dir():
        search_paths.append(mods_dir / CONFIG_FILE_NAME)

    cwd = Path.cwd()
    if cwd != mods_dir:
        search_paths.append(cwd / CONFIG_FILE_NAME)
        search_paths.append(cwd / HIDDEN_CONFIG_FILE_NAME)
    else:
        search_paths.append(cwd / HIDDEN_CONFIG_FILE_NAME)

    for candidate in search_paths:
        if candidate.is_file():
            logger.info(f"Found config file at: {candidate}")
            return candidate

    return None


def load_config(config_path: Path) -> dict[str, Any]:
    logger.info(f"Loading config from: {config_path}")
    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    translation_table = raw.get("translation", {})
    if not isinstance(translation_table, dict):
        logger.warning("Config [translation] section is not a table, ignoring")
        return {}

    config: dict[str, Any] = {}
    for key, value in translation_table.items():
        if key in VALID_CONFIG_KEYS:
            if key == "workers" and not isinstance(value, int | None):
                try:
                    config[key] = int(value)
                except (ValueError, TypeError):
                    logger.warning(f"Config key 'workers' must be an integer, got: {type(value).__name__}")
                    continue
            elif (
                key
                in (
                    "chunk_size",
                    "progress_batch_size",
                    "chunk_token_budget",
                    "chunk_max_text_length",
                )
                and value is not None
            ):
                try:
                    config[key] = int(value)
                except (ValueError, TypeError):
                    logger.warning(f"Config key '{key}' must be an integer, got: {type(value).__name__}")
                    continue
            else:
                config[key] = value
        else:
            logger.warning(f"Unknown config key: '{key}' — ignoring")

    mods_table = raw.get("mods", {})
    if isinstance(mods_table, dict):
        mods_config: dict[str, Any] = {}
        for key, value in mods_table.items():
            if key in VALID_MOD_KEYS:
                if isinstance(value, list):
                    mods_config[key] = [str(v) for v in value]
                elif isinstance(value, str):
                    mods_config[key] = [value]
                else:
                    logger.warning(f"Mods config key '{key}' must be a string or list, ignoring")
            else:
                logger.warning(f"Unknown mods config key: '{key}' — ignoring")
        if mods_config:
            config["mods"] = mods_config

    # Load QA section
    qa_table = raw.get("qa", {})
    if isinstance(qa_table, dict):
        qa_config: dict[str, Any] = {}
        for key, value in qa_table.items():
            if key in VALID_QA_KEYS:
                qa_config[key] = value
            else:
                logger.warning(f"Unknown QA config key: '{key}' — ignoring")
        if qa_config:
            config["qa"] = qa_config

    # Load rate_limit section
    rate_limit_table = raw.get("rate_limit", {})
    if isinstance(rate_limit_table, dict):
        rate_limit_config: dict[str, Any] = {}
        for key, value in rate_limit_table.items():
            if key in VALID_RATE_LIMIT_KEYS:
                rate_limit_config[key] = value
            elif isinstance(value, dict):
                svc_cfg: dict[str, float] = {}
                for svc_key, svc_val in value.items():
                    if svc_key in VALID_RATE_LIMIT_KEYS:
                        svc_cfg[svc_key] = float(svc_val)
                if svc_cfg:
                    rate_limit_config[key] = svc_cfg
            else:
                logger.warning(f"Unknown rate_limit config key: '{key}' — ignoring")
        if rate_limit_config:
            config["rate_limit"] = rate_limit_config

    return config


def save_config(data: dict[str, Any], config_path: Path | None = None) -> Path:
    """Save settings to movamc.toml.

    If config_path is given, overwrites that file.
    Otherwise writes to CWD/movamc.toml.
    Returns the path written to.

    Logs a compact summary of what changed (added / modified / removed keys)
    so you always know what the save actually did.
    """
    target = config_path or (Path.cwd() / CONFIG_FILE_NAME)

    # Snapshot existing file before overwriting so we can show a delta.
    prev: dict[str, Any] = {}
    if target.is_file():
        try:
            with target.open("rb") as f:
                prev = tomllib.load(f)
        except Exception:
            prev = {}

    # Build TOML structure with [translation], [mods], and [qa] sections
    toml_output: dict[str, Any] = {"translation": {}, "mods": {}}

    # Map known translation-level keys
    trans_keys_map = {
        "source": "source",
        "target": "target",
        "provider": "provider",
        "model": "model",
        "workers": "workers",
        "output": "translation_path",
        "path": "mods_path",
        "hint_lang": "hint_lang",
        "glossary_path": "glossary_path",
        "no_cache": "no_cache",
        "output_mode": "output_mode",
        "chunk_mode": "chunk_mode",
        "chunk_size": "chunk_size",
        "chunk_token_budget": "chunk_token_budget",
        "chunk_max_text_length": "chunk_max_text_length",
        "progress_batch_size": "progress_batch_size",
        "ui_locale": "ui_locale",
    }
    for toml_key, data_key in trans_keys_map.items():
        # Prefer internal key (from settings_to_config_dict), fall back to
        # TOML key (from load_config) so both callers work without translating.
        value = data.get(data_key)
        if value is None and toml_key != data_key:
            value = data.get(toml_key)
        if value is not None:
            toml_output["translation"][toml_key] = value

    # Map mods-section keys
    mods_data = data.get("mods", {})
    if isinstance(mods_data, dict):
        for key in ("include", "exclude"):
            if key in mods_data:
                val = mods_data[key]
                if isinstance(val, str):
                    val = [val]
                if isinstance(val, list):
                    toml_output["mods"][key] = val

    # Map QA-section keys
    qa_data = data.get("qa", {})
    if isinstance(qa_data, dict):
        qa_section: dict[str, Any] = {}
        qa_toml_map = {
            "judge": "judge",
            "judge_model": "judge_model",
            "judge_provider": "judge_provider",
            "corrector_model": "corrector_model",
            "threshold": "threshold",
            "max_attempts": "max_attempts",
            "chunk_size": "chunk_size",
            "judge_workers": "judge_workers",
        }
        # Also check flat QA keys
        flat_qa_map = {
            "qa_judge": "judge",
            "qa_judge_model": "judge_model",
            "qa_judge_provider": "judge_provider",
            "qa_corrector_model": "corrector_model",
            "qa_threshold": "threshold",
            "qa_max_attempts": "max_attempts",
            "qa_chunk_size": "chunk_size",
            "qa_judge_workers": "judge_workers",
        }
        for data_key, toml_key in qa_toml_map.items():
            if data_key in qa_data and qa_data[data_key] is not None:
                qa_section[toml_key] = qa_data[data_key]
        for data_key, toml_key in flat_qa_map.items():
            if data_key in data and data[data_key] is not None:
                qa_section[toml_key] = data[data_key]
        if qa_section:
            toml_output["qa"] = qa_section

    rate_limit_data = data.get("rate_limit")
    if isinstance(rate_limit_data, dict) and rate_limit_data:
        toml_output["rate_limit"] = rate_limit_data

    # Remove empty sections before comparison to avoid noise
    toml_output = {k: v for k, v in toml_output.items() if v}

    # Don't touch the file if nothing actually changed.
    # Normalise prev the same way (strip empty tables) for a fair comparison.
    prev_normalised = {k: v for k, v in prev.items() if v}
    if prev_normalised and toml_output == prev_normalised:
        logger.info(f"Saved {target.name} →\n  (no changes — file was identical)")
        return target

    with target.open("wb") as f:
        tomli_w.dump(toml_output, f)

    # Log a compact delta so the user knows what actually changed.
    # Use normalised prev so empty-section removals don't show as spurious deltas.
    _log_config_delta(prev_normalised, toml_output, target)
    return target


def _log_config_delta(prev: dict[str, Any], curr: dict[str, Any], target: Path) -> None:
    """Log which top-level sections / keys were added, changed, or removed."""

    def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        flat: dict[str, Any] = {}
        for k, v in d.items():
            full = f"{prefix}{k}" if prefix else k
            if isinstance(v, dict) and not isinstance(v, list):
                flat.update(_flatten(v, f"{full}."))
            else:
                flat[full] = v
        return flat

    old_flat = _flatten(prev)
    new_flat = _flatten(curr)

    added = {k: v for k, v in new_flat.items() if k not in old_flat}
    removed = {k: v for k, v in old_flat.items() if k not in new_flat}
    changed = {k: (old_flat[k], new_flat[k]) for k in new_flat if k in old_flat and old_flat[k] != new_flat[k]}

    lines: list[str] = [f"Saved {target.name} →"]
    if added:
        for k, v in sorted(added.items()):
            lines.append(f"  + {k} = {_fmt_val(v)}")
    if changed:
        for k, (old, new) in sorted(changed.items()):
            lines.append(f"  ~ {k}: {_fmt_val(old)} → {_fmt_val(new)}")
    if removed:
        for k, v in sorted(removed.items()):
            lines.append(f"  - {k}  (was {_fmt_val(v)})")

    if not added and not changed and not removed:
        lines.append("  (no changes — file was identical)")

    logger.info("\n".join(lines))


def _fmt_val(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(repr(x) for x in v) + "]"
    return str(v)


def generate_config_template(output_dir: str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    config_path = out / CONFIG_FILE_NAME
    config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    logger.info(f"Generated config template at: {config_path}")
    return config_path
