"""Provider registration, discovery, and availability checking.

New providers self-register using the @register_provider decorator
so the factory can discover them without a hard-coded if/elif chain.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...application.ports import TranslationProvider
from ...core.dotenv_loader import load_dotenv_files

if TYPE_CHECKING:
    from .openai_like import LLMTransport

PROVIDER_FACTORIES: dict[str, Callable[..., TranslationProvider]] = {}
"""Registry of provider-name → factory-function.

Each factory accepts **kwargs matching the superset of parameters
that :func:`build_transport` can pass. Unknown kwargs are
ignored so a simple provider only needs to accept the few it uses.
"""

PROVIDER_LABELS: dict[str, str] = {}
"""Human-readable labels for UI dropdowns."""


def register_provider(
    name: str,
    *,
    label: str = "",
) -> Callable[[Callable[..., TranslationProvider]], Callable[..., TranslationProvider]]:
    """Decorator that registers a provider factory under *name*.

    Usage::

        @register_provider("myengine", label="My Engine v2")
        def build_my_engine(**kwargs) -> TranslationProvider:
            ...
    """

    def decorator(fn: Callable[..., TranslationProvider]) -> Callable[..., TranslationProvider]:
        PROVIDER_FACTORIES[name] = fn
        if label:
            PROVIDER_LABELS[name] = label
        return fn

    return decorator


AI_PROVIDERS: frozenset[str] = frozenset({
    "openai", "anthropic", "gemini", "ollama", "litellm", "openaicompatible", "opencode",
})
"""Provider names that use LLM-based translation (as opposed to Google)."""

ALL_PROVIDERS: frozenset[str] = frozenset({
    "google", "openai", "anthropic", "gemini", "ollama", "litellm", "openaicompatible", "opencode",
})
"""Every known built-in provider name."""


def _register_builtins() -> None:
    """Import and register all built-in provider factories.

    Called once at module init to populate the registry with the
    providers shipped with mova-mc.
    """
    # Google ------------------------------------------------------------
    @register_provider("google", label="Google Translate")
    def _build_google(**kwargs: Any) -> TranslationProvider:
        from .google import GoogleProvider

        return GoogleProvider(
            source_lang=kwargs["source_lang"],
            target_lang=kwargs["target_lang"],
            capitalize=kwargs.get("capitalize", True),
            max_retries=kwargs.get("max_retries", 3),
            max_concurrent_chunks=kwargs.get("max_concurrent_chunks", 4),
        )

    # OpenAI-like providers ----------------------------------------------
    @register_provider("openai", label="OpenAI (GPT-4o-mini)")
    def _build_openai(**kwargs: Any) -> TranslationProvider:
        kwargs.pop("provider", None)
        return _build_openai_like("openai", **kwargs)

    @register_provider("anthropic", label="Anthropic Claude")
    def _build_anthropic(**kwargs: Any) -> TranslationProvider:
        kwargs.pop("provider", None)
        return _build_openai_like("anthropic", **kwargs)

    @register_provider("gemini", label="Google Gemini")
    def _build_gemini(**kwargs: Any) -> TranslationProvider:
        kwargs.pop("provider", None)
        return _build_openai_like("gemini", **kwargs)

    @register_provider("ollama", label="Ollama (Local)")
    def _build_ollama(**kwargs: Any) -> TranslationProvider:
        kwargs.pop("provider", None)
        return _build_openai_like("ollama", **kwargs)

    @register_provider("litellm", label="LiteLLM")
    def _build_litellm(**kwargs: Any) -> TranslationProvider:
        kwargs.pop("provider", None)
        return _build_openai_like("litellm", **kwargs)

    @register_provider("openaicompatible", label="OpenAI-Compatible")
    def _build_openaicompatible(**kwargs: Any) -> TranslationProvider:
        kwargs.pop("provider", None)
        return _build_openai_like("openaicompatible", **kwargs)

    @register_provider("opencode", label="OpenCode Go")
    def _build_opencode(**kwargs: Any) -> TranslationProvider:
        kwargs.pop("provider", None)
        return _build_openai_like("opencode", **kwargs)


def build_transport(provider: str, model: str | None = None) -> LLMTransport:
    """Build and return a configured ``LLMTransport`` for the given *provider*.

    Resolves the model via :func:`_resolve_model` and selects the appropriate
    transport class (``OpenAICompatTransport`` / ``OpenAISDKTransport`` /
    ``LitellmTransport``).

    This is a public helper so that judge/corrector utilities can reuse the
    same transport selection logic without building a full translator.
    """
    from .openai_like import LLMTransport  # noqa: F401
    from .transports.compat_sdk import OpenAICompatTransport
    from .transports.litellm_sdk import LitellmTransport
    from .transports.openai_sdk import OpenAISDKTransport
    from .transports.opencode import OpenCodeTransport

    resolved_model: str = _resolve_model(provider, model)  # type: ignore[arg-type]

    # Auto-prepend provider prefix for Ollama (LiteLLM requires it)
    if provider == "ollama" and resolved_model and not resolved_model.startswith("ollama/"):
        resolved_model = f"ollama/{resolved_model}"

    if provider == "opencode":
        return OpenCodeTransport(model=resolved_model)

    if provider == "openaicompatible":
        base_url = os.getenv("OPENAICOMPATIBLE_BASE_URL", "")
        return OpenAICompatTransport(model=resolved_model, base_url=base_url)
    if provider == "openai":
        try:
            return OpenAISDKTransport(model=resolved_model)
        except (ImportError, ValueError) as e:
            from loguru import logger

            logger.warning(
                "OpenAI direct client unavailable ({}), falling back to LiteLLM. "
                "To avoid this, install: pip install openai",
                e,
            )
            return LitellmTransport(model=resolved_model)
    return LitellmTransport(model=resolved_model)


def _build_openai_like(provider: str, **kwargs: Any) -> TranslationProvider:
    """Build an OpenAILikeProvider for the given *provider* name."""
    from .openai_like import OpenAILikeProvider

    resolved_model = _resolve_model(provider, kwargs.get("model"))
    transport = build_transport(provider, resolved_model)
    resolved_chunk_size = kwargs.get("chunk_size")
    if resolved_chunk_size is None:
        resolved_chunk_size = 10 if provider == "openaicompatible" else 25

    return OpenAILikeProvider(
        source_lang=kwargs.get("source_lang", ""),
        target_lang=kwargs.get("target_lang", ""),
        transport=transport,
        service_name=provider if provider != "openaicompatible" else "openaicompatible",
        capitalize=kwargs.get("capitalize", True),
        max_retries=kwargs.get("max_retries", 3),
        chunk_size=resolved_chunk_size,
        max_concurrent_chunks=kwargs.get("max_concurrent_chunks", 4),
        chunk_token_budget=kwargs.get("chunk_token_budget", 3500),
        chunk_max_text_length=kwargs.get("chunk_max_text_length", 200),
        chunk_mode=kwargs.get("chunk_mode", "auto"),
        source_lang_display=kwargs.get("source_lang_display"),
        target_lang_display=kwargs.get("target_lang_display"),
        glossary=kwargs.get("glossary"),
    )


def _resolve_model(provider: str, explicit: str | None = None) -> str:
    if explicit:
        if provider == "opencode":
            from .transports.opencode import normalize_opencode_model

            return normalize_opencode_model(explicit)
        return explicit
    env_model = os.getenv("TRANSLATION_MODEL")
    if env_model:
        if provider == "opencode":
            from .transports.opencode import normalize_opencode_model

            return normalize_opencode_model(env_model)
        return env_model
    if provider == "openai":
        return os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    if provider == "openaicompatible":
        return os.getenv("OPENAICOMPATIBLE_MODEL") or "gpt-4o-mini"
    if provider == "opencode":
        from .transports.opencode import normalize_opencode_model

        raw = os.getenv("OPENCODE_GO_MODEL") or "deepseek-v4-flash"
        return normalize_opencode_model(raw)
    _PROVIDER_DEFAULTS: dict[str, str] = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-haiku-20240307",
        "gemini": "gemini/gemini-1.5-flash",
        "ollama": "ollama/llama3",
        "litellm": "gpt-4o-mini",
    }
    return _PROVIDER_DEFAULTS.get(provider, "gpt-4o-mini")


# Initialise built-in registry on import
_register_builtins()


def _try_load_dotenv() -> None:
    load_dotenv_files()


def check_provider_available(provider: str) -> tuple[bool, str]:
    """Check whether *provider* is available (deps installed + keys configured)."""
    if provider == "google":
        try:
            from deep_translator import GoogleTranslator  # noqa: F401

            return True, "Always available"
        except ImportError:
            return False, "Package not installed (pip install deep-translator)"

    _try_load_dotenv()

    if provider == "openaicompatible":
        try:
            import openai
        except ImportError:
            return False, "OpenAI package not installed (pip install openai python-dotenv)"
        api_key = os.getenv("OPENAICOMPATIBLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAICOMPATIBLE_BASE_URL")
        if not api_key:
            return False, "OPENAICOMPATIBLE_API_KEY not found (.env file or environment variable)"
        if not base_url:
            return False, "OPENAICOMPATIBLE_BASE_URL not found (.env file or environment variable)"
        model = os.getenv("OPENAICOMPATIBLE_MODEL") or "gpt-4o-mini"
        return True, f"Available (base_url={base_url}, model={model})"

    if provider == "opencode":
        try:
            import httpx  # noqa: F401
            import openai
        except ImportError as e:
            return False, f"Required package not installed (pip install mova-mc[ai]): {e.name}"
        api_key = os.getenv("OPENCODE_GO_API_KEY")
        if not api_key:
            return False, "OPENCODE_GO_API_KEY not found (.env file or environment variable)"
        from .transports.opencode import OPENCODE_GO_BASE_URL, normalize_opencode_model

        base_url = os.getenv("OPENCODE_GO_BASE_URL") or OPENCODE_GO_BASE_URL
        model = normalize_opencode_model(os.getenv("OPENCODE_GO_MODEL") or "deepseek-v4-flash")
        return True, f"Available (base_url={base_url}, model={model})"

    if provider == "openai":
        openai_ok = False
        try:
            import openai  # noqa: F401
            openai_ok = True
        except ImportError:
            pass
        litellm_ok = False
        try:
            import litellm
            litellm_ok = True
        except ImportError:
            pass
        if not openai_ok and not litellm_ok:
            return False, "OpenAI or LiteLLM package not installed (pip install openai litellm python-dotenv)"
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            return True, "Available (OPENAI_API_KEY configured)"
        return False, "OPENAI_API_KEY not found (.env file or environment variable)"

    litellm_ok = False
    try:
        import litellm  # noqa: F401
        litellm_ok = True
    except ImportError:
        pass

    if not litellm_ok:
        return False, "LiteLLM package not installed (pip install litellm python-dotenv)"

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            return True, "Available (ANTHROPIC_API_KEY configured)"
        return False, "ANTHROPIC_API_KEY not found (.env file or environment variable)"

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            return True, "Available (GEMINI_API_KEY configured)"
        return False, "GEMINI_API_KEY not found (.env file or environment variable)"

    if provider == "ollama":
        base_url = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
        return True, f"Available (using {base_url})"

    if provider == "litellm":
        model = os.getenv("TRANSLATION_MODEL") or "gpt-4o-mini"
        return True, f"Available (model: {model})"

    return False, f"Unknown provider: {provider}"
