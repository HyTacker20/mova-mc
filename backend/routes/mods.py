"""GET /api/mods — scan a mods directory and return ModInfo list."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from app.core.mod_scanner import ModScanner
from backend.routes.config import _resolve_path
from backend.schemas import ModInfoResponse, ScanResponse

router = APIRouter()

# Language codes are always two lowercase letters, underscore, two uppercase
# letters (e.g. "en_US", "uk_UA").
_LANG_CODE_RE = re.compile(r"^[a-z]{2}_[A-Z]{2}$")


@router.get("/mods", response_model=ScanResponse)
def scan_mods(path: str = "./mods", source: str = "en_US") -> ScanResponse:
    """Scan *path* for JAR files and return their metadata."""
    # --- input validation ---
    if not _LANG_CODE_RE.match(source):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid language code: {source!r}. Expected format: xx_XX (e.g. en_US, uk_UA)",
        )

    try:
        mods_dir = _resolve_path(path)
    except (ValueError, HTTPException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        scanner = ModScanner(str(mods_dir), source_lang=source)
        mods = scanner.discover_mods()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mod_responses = [
        ModInfoResponse(
            name=m.name,
            size_bytes=m.size_bytes,
            has_lang_files=m.has_lang_files,
            lang_file_count=m.lang_file_count,
            estimated_entries=m.estimated_entries,
            selected=m.selected,
        )
        for m in mods
    ]
    return ScanResponse(
        mods=mod_responses,
        total=len(mod_responses),
        selected=sum(1 for m in mod_responses if m.selected),
    )
