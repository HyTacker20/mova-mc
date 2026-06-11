"""GET /api/mods — scan a mods directory and return ModInfo list."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.mod_scanner import ModScanner
from backend.schemas import ModInfoResponse, ScanResponse

router = APIRouter()


@router.get("/mods", response_model=ScanResponse)
def scan_mods(path: str = "./mods") -> ScanResponse:
    """Scan *path* for JAR files and return their metadata."""
    try:
        scanner = ModScanner(path)
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
