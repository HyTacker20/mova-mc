"""Live model list fetching per provider with fallback to hardcoded lists.

Each provider's REST API (or SDK) is queried asynchronously via httpx.
Results are cached in-memory for the session so we don't re-fetch on
every provider switch.  On any error (network, auth, missing deps) we
silently fall back to the curated list in FALLBACK_MODELS.
"""

from __future__ import annotations

import asyncio
import os

try:
    import httpx

    HAS_HTTPX = True
except ImportError:  # pragma: no cover
    HAS_HTTPX = False


# ── Fallback model lists (used when live fetch fails) ─────────────

FALLBACK_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "o3-mini",
        "o4-mini",
        "gpt-4-turbo",
    ],
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3.5-sonnet-20241022",
        "claude-3-haiku-20240307",
    ],
    "gemini": [
        "gemini/gemini-3.5-flash",
        "gemini/gemini-3.1-pro",
        "gemini/gemini-3-flash",
        "gemini/gemini-3.1-flash-lite",
        "gemini/gemini-2.5-flash",
        "gemini/gemini-2.5-pro",
        "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-2.0-flash",
        "gemini/gemini-2.0-flash-lite",
        "gemini/gemini-1.5-flash",
        "gemini/gemini-1.5-pro",
    ],
    "ollama": [
        "ollama/llama3",
        "ollama/llama3.1",
        "ollama/llama3.2",
        "ollama/mistral",
        "ollama/codellama",
    ],
    "litellm": [
        "gpt-4o-mini",
        "gpt-4o",
        "claude-sonnet-4-20250514",
        "gemini/gemini-2.0-flash",
    ],
    "openaicompatible": [
        "gpt-4o-mini",
        "gpt-4o",
        "claude-sonnet-4-20250514",
    ],
    "opencode": [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "glm-5.1",
        "glm-5",
        "kimi-k2.5",
        "kimi-k2.6",
        "mimo-v2.5",
        "mimo-v2.5-pro",
        "minimax-m3",
        "minimax-m2.7",
        "minimax-m2.5",
        "qwen3.7-max",
        "qwen3.7-plus",
        "qwen3.6-plus",
    ],
}

# ── Session cache ─────────────────────────────────────────────────

_model_cache: dict[str, list[str]] = {}

_DEFAULT_TIMEOUT = 15  # seconds


# ── Per-provider fetchers ─────────────────────────────────────────


async def _fetch_openai(api_key: str) -> list[str]:
    """Fetch available models from OpenAI."""
    if not HAS_HTTPX:
        return []
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", []) if m.get("id")]


async def _fetch_anthropic(api_key: str) -> list[str]:
    """Fetch available models from Anthropic."""
    if not HAS_HTTPX:
        return []
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", []) if m.get("id")]


async def _fetch_gemini(api_key: str) -> list[str]:
    """Fetch available models from Google Gemini REST API."""
    if not HAS_HTTPX:
        return []
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        models: list[str] = []
        for m in data.get("models", []):
            name: str = m.get("name", "")
            # names look like "models/gemini-2.0-flash" → "gemini/gemini-2.0-flash"
            if name.startswith("models/"):
                short = name[len("models/") :]
                # Only include generateContent-supported models
                supported_actions = m.get("supportedGenerationMethods", [])
                if "generateContent" in supported_actions:
                    models.append(f"gemini/{short}")
        return models


async def _fetch_ollama(base_url: str) -> list[str] | None:
    """Fetch installed models from the Ollama server.

    Tries the HTTP ``/api/tags`` endpoint first (respects *base_url*),
    then falls back to the ``ollama list`` CLI.

    Returns ``None`` when Ollama is unreachable.
    Returns an empty list when the server responds but has no models.
    """
    import subprocess

    url = (base_url or "http://localhost:11434").rstrip("/")

    if HAS_HTTPX:
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                resp = await client.get(f"{url}/api/tags")
                resp.raise_for_status()
                models: list[str] = []
                for m in resp.json().get("models", []):
                    name = m.get("name", "")
                    if name:
                        models.append(f"ollama/{name}")
                return models
        except Exception:
            pass

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=_DEFAULT_TIMEOUT,
        )
        if result.returncode != 0:
            return None
        models = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("NAME"):
                continue
            name = line.split(maxsplit=1)[0] if line else ""
            if name:
                models.append(f"ollama/{name}")
        return models
    except Exception:
        return None


async def _fetch_opencode(base_url: str, api_key: str) -> list[str]:
    """Fetch models from OpenCode Go.

    OpenCode Go's /models endpoint returns the full OpenRouter catalog
    with provider-prefixed names (e.g. ``deepseek/deepseek-v4-pro``),
    but the chat API expects bare model IDs (e.g. ``deepseek-v4-pro``).
    Since the prefixed names are not usable and the set of OpenCode-native
    models is curated and stable, we return the hardcoded fallback list
    rather than fetching a misleading /models response.
    """
    # The fallback list is the authoritative set of OpenCode Go model IDs.
    return list(FALLBACK_MODELS.get("opencode", []))


async def _fetch_openaicompatible(base_url: str, api_key: str) -> list[str]:
    """Fetch models from an OpenAI-compatible endpoint."""
    if not HAS_HTTPX or not base_url:
        return []
    url = base_url.rstrip("/") + "/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", []) if m.get("id")]


# ── Public API ────────────────────────────────────────────────────


async def fetch_models(
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
    *,
    force_refresh: bool = False,
) -> list[str]:
    """Fetch live model list for *provider*, cached per session.

    Parameters override env vars when provided (used by the TUI when
    the user types credentials manually).

    On failure: most providers fall back to FALLBACK_MODELS so the
    UI is never broken by a network hiccup.  Ollama always returns
    only locally installed models (empty list when unreachable or
    no models installed).
    """
    provider = provider.lower()

    # Return cached result if available
    if not force_refresh and provider in _model_cache:
        return list(_model_cache[provider])

    # Resolve api_key / base_url from params → env → None
    resolved_key = api_key or _env_api_key(provider)
    resolved_url = base_url or _env_base_url(provider)

    # For Ollama: None = unreachable → return empty (no fallback)
    if provider == "ollama":
        local = await _fetch_ollama(resolved_url)
        if local is not None:
            # Successful response — use result even if empty
            _model_cache[provider] = local
            return list(local)
        # Ollama unreachable — do not cache failures (keeps prior list in UI)
        return []
    else:
        try:
            models: list[str] = []
            if provider == "openai" and resolved_key:
                models = await _fetch_openai(resolved_key)
            elif provider == "anthropic" and resolved_key:
                models = await _fetch_anthropic(resolved_key)
            elif provider == "gemini" and resolved_key:
                models = await _fetch_gemini(resolved_key)
            elif provider == "openaicompatible" and resolved_url:
                models = await _fetch_openaicompatible(resolved_url, resolved_key or "")
            elif provider == "opencode" and resolved_key:
                from .transports.opencode import OPENCODE_GO_BASE_URL

                url = resolved_url or os.getenv("OPENCODE_GO_BASE_URL") or OPENCODE_GO_BASE_URL
                models = await _fetch_opencode(url, resolved_key)
            if models:
                _model_cache[provider] = models
                return list(models)
        except Exception:
            pass

    # Fallback
    fallback = list(FALLBACK_MODELS.get(provider, []))
    _model_cache[provider] = fallback
    return fallback


def get_cached_models(provider: str) -> list[str] | None:
    """Return the session-cached model list for *provider*, if any."""
    cached = _model_cache.get(provider.lower())
    if cached is None:
        return None
    return list(cached)


def clear_model_cache(provider: str | None = None) -> None:
    """Clear cached model list for *provider* (or all providers)."""
    if provider:
        _model_cache.pop(provider.lower(), None)
    else:
        _model_cache.clear()


# ── Internal helpers ──────────────────────────────────────────────


def _env_api_key(provider: str) -> str:
    _MAP: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openaicompatible": "OPENAICOMPATIBLE_API_KEY",
        "opencode": "OPENCODE_GO_API_KEY",
    }
    var = _MAP.get(provider)
    return os.getenv(var, "") if var else ""


def _env_base_url(provider: str) -> str:
    _MAP: dict[str, str] = {
        "ollama": "OLLAMA_API_BASE",
        "openaicompatible": "OPENAICOMPATIBLE_BASE_URL",
        "opencode": "OPENCODE_GO_BASE_URL",
    }
    _DEFAULTS: dict[str, str] = {
        "ollama": "http://localhost:11434",
        "opencode": "https://opencode.ai/zen/go/v1",
    }
    var = _MAP.get(provider)
    if not var:
        return ""
    return os.getenv(var) or _DEFAULTS.get(provider, "")
