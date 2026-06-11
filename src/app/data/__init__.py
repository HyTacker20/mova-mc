"""Data resource loading — language lists, glossary files."""

import json
from pathlib import Path
from typing import Any


def load_languages() -> list[dict[str, Any]]:
    """Load the canonical language list from ``languages.json``.

    This is the single source of truth for the list of supported languages
    and their Minecraft locale codes.  The :mod:`app.domain.languages`
    module loads this at import time and exposes helper functions.
    """
    path = Path(__file__).parent / "languages.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]
