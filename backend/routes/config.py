"""GET/POST /api/config — load and save settings to movamc.toml."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config_loader import (
    find_config_file,
    load_config,
    save_config,
)

router = APIRouter()


class ConfigPayload(BaseModel):
    """Fields the web UI can persist to movamc.toml."""

    provider: str | None = None
    model: str | None = None
    # Path used to discover/place the config file
    mods_path: str = "./mods"


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


def _resolve_path(mods_path: str) -> Path:
    """Resolve a relative path against CWD to get an absolute directory."""
    p = Path(mods_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


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
    )


@router.post("/config", status_code=200)
def post_config(payload: ConfigPayload) -> dict[str, str]:
    """Save the given fields to movamc.toml."""
    mods_dir = _resolve_path(payload.mods_path)
    existing = find_config_file(str(mods_dir))

    # Start with existing settings if available
    data: dict = {}
    if existing is not None:
        try:
            data = load_config(existing)
        except Exception:
            pass

    # Merge in new values
    if payload.provider is not None:
        data["provider"] = payload.provider
    if payload.model is not None:
        data["model"] = payload.model
    if payload.mods_path:
        data["path"] = payload.mods_path

    try:
        saved = save_config(data, existing)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {exc}") from exc

    return {"status": "ok", "config_path": str(saved)}
