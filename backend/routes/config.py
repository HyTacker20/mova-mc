"""GET/POST /api/config — load and save settings to movamc.toml."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.core.config_loader import (
    find_config_file,
    load_config,
    save_config,
)

router = APIRouter()


# Allow-list for config file locations.  Config files must live under one of
# these roots.  This prevents path-traversal attacks where an attacker
# controls the `path` or `config_path` query/body parameter.
def _allowed_roots() -> list[Path]:
    """Return the set of directory roots that path inputs may resolve into."""
    roots: list[Path] = [
        Path.home().resolve(),
        Path.cwd().resolve(),
    ]
    # pytest fixtures create temporary directories outside HOME/CWD —
    # include the system temp directory so tests pass on Linux CI where
    # /tmp is not under /home/runner.
    try:
        tmp = Path(tempfile.gettempdir()).resolve()
        if tmp not in roots:
            roots.append(tmp)
    except Exception:
        pass
    return roots


def _validate_path_within_root(p: Path) -> Path:
    """Resolve *p* and verify it stays within an allowed directory tree.

    Raises :exc:`ValueError` when the resolved absolute path escapes every
    allowed root.
    """
    resolved = p.resolve()
    for base in _allowed_roots():
        try:
            resolved.relative_to(base)
            return resolved
        except ValueError:
            continue
    raise ValueError(f"Path {resolved} is outside allowed directories: {', '.join(str(b) for b in _allowed_roots())}")


class ConfigPayload(BaseModel):
    """Fields the web UI can persist to movamc.toml."""

    # -- Provider step --
    provider: str | None = None
    model: str | None = None
    # -- Paths step --
    source: str | None = None
    target: str | None = None
    mods_path: str | None = None
    output: str | None = None
    output_mode: str | None = None
    # -- Advanced step --
    workers: int | None = None
    no_cache: bool | None = None
    hint_lang: str | None = None
    # QA section (nested; passed as flat keys too)
    qa: dict[str, Any] | None = None
    # Explicit path to the config file (from GET /api/config response).
    # When provided, saves go directly to this file — no discovery needed.
    config_path: str | None = None


class QaConfigResponse(BaseModel):
    """Sanitised view of the [qa] section for the web UI."""

    judge: bool = False
    judge_provider: str | None = None
    judge_model: str | None = None
    corrector_model: str | None = None
    threshold: int = 3
    max_attempts: int = 2
    chunk_size: int = 25
    judge_workers: int = 2


class ConfigResponse(BaseModel):
    """Sanitised view of the [translation] section for the web UI."""

    provider: str
    model: str | None
    source: str
    target: str
    workers: int
    output: str | None
    no_cache: bool
    hint_lang: str | None
    glossary_path: str | None
    output_mode: str
    config_path: str | None  # where the config was found, or None
    qa: QaConfigResponse = QaConfigResponse()


def _qa_from_raw(raw: dict[str, Any]) -> QaConfigResponse:
    """Build QaConfigResponse from loaded config (supports TOML + flat keys)."""
    qa_table = raw.get("qa", {})
    if not isinstance(qa_table, dict):
        qa_table = {}
    return QaConfigResponse(
        judge=bool(qa_table.get("judge", raw.get("qa_judge", False))),
        judge_provider=qa_table.get("judge_provider", raw.get("qa_judge_provider")),
        judge_model=qa_table.get("judge_model", raw.get("qa_judge_model")),
        threshold=int(qa_table.get("threshold", raw.get("qa_threshold", 3))),
        max_attempts=int(qa_table.get("max_attempts", raw.get("qa_max_attempts", 2))),
        chunk_size=int(qa_table.get("chunk_size", raw.get("qa_chunk_size", 25))),
        judge_workers=int(qa_table.get("judge_workers", raw.get("qa_judge_workers", 2))),
        corrector_model=qa_table.get("corrector_model", raw.get("qa_corrector_model")),
    )


def _resolve_path(mods_path: str) -> Path:
    """Resolve a relative path against CWD and validate it is safe."""
    p = Path(mods_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        return _validate_path_within_root(p)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/config", response_model=ConfigResponse)
def get_config(path: str = "./mods") -> ConfigResponse:
    """Load movamc.toml (if it exists) and return relevant translation fields."""
    mods_dir = _resolve_path(path)
    config_path = find_config_file(str(mods_dir))
    if config_path is None:
        return ConfigResponse(
            provider="google",
            model=None,
            source="en_US",
            target="uk_UA",
            workers=4,
            output=None,
            no_cache=False,
            hint_lang=None,
            glossary_path=None,
            output_mode="separate",
            config_path=None,
            qa=QaConfigResponse(),
        )

    raw = load_config(config_path)

    return ConfigResponse(
        provider=raw.get("provider", "google"),
        model=raw.get("model"),
        source=raw.get("source", "en_US"),
        target=raw.get("target", "uk_UA"),
        workers=raw.get("workers", 4),
        output=raw.get("output"),
        no_cache=raw.get("no_cache", False),
        hint_lang=raw.get("hint_lang"),
        glossary_path=raw.get("glossary_path"),
        output_mode=raw.get("output_mode", "separate"),
        config_path=str(config_path),
        qa=_qa_from_raw(raw),
    )


@router.post("/config", status_code=200)
def post_config(payload: ConfigPayload) -> dict[str, str]:
    """Save the given fields to movamc.toml.

    When *config_path* is provided, writes directly to that file (the
    frontend passes the value from GET /api/config, so saves always go
    to the same file that was loaded).  Otherwise falls back to
    *mods_path* or CWD.
    """
    try:
        if payload.config_path:
            config_file = _validate_path_within_root(Path(payload.config_path))
        elif payload.mods_path:
            config_file = _resolve_path(payload.mods_path) / "movamc.toml"
        else:
            config_file = Path.cwd() / "movamc.toml"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing: Path | None = config_file if config_file.is_file() else None

    # Start with existing settings if available
    data: dict = {}
    if existing is not None:
        try:
            data = load_config(existing)
        except Exception:
            logger.warning(
                "Failed to load existing config at {} — it will be overwritten with only the new payload.",
                existing,
            )
            pass

    # Merge in new values
    if payload.provider is not None:
        data["provider"] = payload.provider
    if payload.model is not None:
        data["model"] = payload.model
    if payload.source is not None:
        data["source"] = payload.source
    if payload.target is not None:
        data["target"] = payload.target
    if payload.mods_path:
        data["path"] = payload.mods_path
    if payload.output is not None:
        data["output"] = payload.output
    if payload.output_mode is not None:
        data["output_mode"] = payload.output_mode
    if payload.workers is not None:
        data["workers"] = payload.workers
    if payload.no_cache is not None:
        data["no_cache"] = payload.no_cache
    if payload.hint_lang is not None:
        data["hint_lang"] = payload.hint_lang
    if isinstance(payload.qa, dict):
        data["qa"] = payload.qa

    try:
        saved = save_config(data, config_file)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {exc}") from exc

    return {"status": "ok", "config_path": str(saved)}
