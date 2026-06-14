"""Tests for model_list.py — live fetching, caching, fallback lists, env var resolution."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.providers.model_list import (
    FALLBACK_MODELS,
    _env_api_key,
    _env_base_url,
    _fetch_anthropic,
    _fetch_gemini,
    _fetch_ollama,
    _fetch_openai,
    _fetch_openaicompatible,
    _fetch_opencode,
    clear_model_cache,
    fetch_models,
    get_cached_models,
)


# ── FALLBACK_MODELS ──────────────────────────────────────────────────

class TestFallbackModels:
    def test_has_all_providers(self) -> None:
        """Every major provider has a fallback list."""
        for provider in ("openai", "anthropic", "gemini", "ollama", "litellm", "openaicompatible", "opencode"):
            assert provider in FALLBACK_MODELS
            assert isinstance(FALLBACK_MODELS[provider], list)
            assert len(FALLBACK_MODELS[provider]) > 0

    def test_openai_models(self) -> None:
        assert "gpt-4o-mini" in FALLBACK_MODELS["openai"]
        assert "gpt-4o" in FALLBACK_MODELS["openai"]

    def test_anthropic_models(self) -> None:
        assert any("claude" in m for m in FALLBACK_MODELS["anthropic"])

    def test_gemini_models(self) -> None:
        assert any("gemini" in m for m in FALLBACK_MODELS["gemini"])


# ── _env_api_key ─────────────────────────────────────────────────────

class TestEnvApiKey:
    def test_openai_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert _env_api_key("openai") == "sk-test"

    def test_anthropic_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
        assert _env_api_key("anthropic") == "ant-test"

    def test_gemini_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "gem-test")
        assert _env_api_key("gemini") == "gem-test"

    def test_openaicompatible_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAICOMPATIBLE_API_KEY", "compat-test")
        assert _env_api_key("openaicompatible") == "compat-test"

    def test_opencode_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENCODE_GO_API_KEY", "oc-test")
        assert _env_api_key("opencode") == "oc-test"

    def test_unknown_provider_returns_empty(self) -> None:
        assert _env_api_key("unknown_provider") == ""

    def test_missing_env_var_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert _env_api_key("openai") == ""


# ── _env_base_url ────────────────────────────────────────────────────

class TestEnvBaseUrl:
    def test_ollama_default(self) -> None:
        assert _env_base_url("ollama") == "http://localhost:11434"

    def test_ollama_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_API_BASE", "http://my-ollama:9999")
        assert _env_base_url("ollama") == "http://my-ollama:9999"

    def test_openaicompatible_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAICOMPATIBLE_BASE_URL", "https://my-api.example.com/v1")
        assert _env_base_url("openaicompatible") == "https://my-api.example.com/v1"

    def test_openaicompatible_default_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAICOMPATIBLE_BASE_URL", raising=False)
        assert _env_base_url("openaicompatible") == ""

    def test_opencode_default(self) -> None:
        result = _env_base_url("opencode")
        # Default or from env
        assert isinstance(result, str)

    def test_unknown_provider_returns_empty(self) -> None:
        assert _env_base_url("unknown_provider") == ""


# ── Cache helpers ────────────────────────────────────────────────────

class TestCacheHelpers:
    def test_get_cached_models_none(self) -> None:
        clear_model_cache()  # ensure clean
        assert get_cached_models("openai") is None

    def test_get_cached_models_after_fetch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clear_model_cache()
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with patch("app.infrastructure.providers.model_list._fetch_openai") as mock_fetch:
            mock_fetch.return_value = ["gpt-4o", "gpt-4o-mini"]
            import asyncio
            asyncio.run(fetch_models("openai", api_key="sk-test"))

        cached = get_cached_models("openai")
        assert cached == ["gpt-4o", "gpt-4o-mini"]

        # get_cached_models returns a copy, not the internal list
        cached.append("extra")
        assert get_cached_models("openai") == ["gpt-4o", "gpt-4o-mini"]

    def test_clear_specific_provider(self) -> None:
        clear_model_cache()
        # Populate cache manually via internal
        from app.infrastructure.providers.model_list import _model_cache
        _model_cache["openai"] = ["m1"]
        _model_cache["anthropic"] = ["m2"]

        clear_model_cache("openai")
        assert "openai" not in _model_cache
        assert "anthropic" in _model_cache

        clear_model_cache()  # clear all
        assert "anthropic" not in _model_cache

    def test_clear_all(self) -> None:
        from app.infrastructure.providers.model_list import _model_cache
        _model_cache["openai"] = ["m1"]
        _model_cache["anthropic"] = ["m2"]

        clear_model_cache()
        assert len(_model_cache) == 0

    def test_clear_nonexistent_provider(self) -> None:
        """Clearing a provider not in cache is a no-op."""
        clear_model_cache()
        clear_model_cache("nonexistent")  # should not raise


# ── _fetch_opencode ──────────────────────────────────────────────────

class TestFetchOpencode:
    @pytest.mark.asyncio
    async def test_returns_fallback_list(self) -> None:
        result = await _fetch_opencode("https://opencode.ai", "key123")
        assert isinstance(result, list)
        assert len(result) > 0
        assert "deepseek-v4-pro" in result or "deepseek-v4-flash" in result


# ── fetch_models ─────────────────────────────────────────────────────

class TestFetchModels:
    def teardown_method(self) -> None:
        clear_model_cache()

    @pytest.mark.asyncio
    async def test_openai_live(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch_models with OpenAI provider and live fetch success."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with patch("app.infrastructure.providers.model_list._fetch_openai") as mock_fetch:
            mock_fetch.return_value = ["gpt-4o", "gpt-4o-mini"]
            models = await fetch_models("openai")

        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models

    @pytest.mark.asyncio
    async def test_openai_fallback_on_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When live fetch fails, fallback models are returned."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with patch("app.infrastructure.providers.model_list._fetch_openai", side_effect=RuntimeError("network error")):
            models = await fetch_models("openai")

        # Should have fallback models
        assert len(models) > 0
        assert "gpt-4o-mini" in models

    @pytest.mark.asyncio
    async def test_anthropic_live(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")

        with patch("app.infrastructure.providers.model_list._fetch_anthropic") as mock_fetch:
            mock_fetch.return_value = ["claude-sonnet-4"]
            models = await fetch_models("anthropic")

        assert "claude-sonnet-4" in models

    @pytest.mark.asyncio
    async def test_gemini_live(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "gem-test")

        with patch("app.infrastructure.providers.model_list._fetch_gemini") as mock_fetch:
            mock_fetch.return_value = ["gemini/gemini-2.5-flash"]
            models = await fetch_models("gemini")

        assert "gemini/gemini-2.5-flash" in models

    @pytest.mark.asyncio
    async def test_ollama_success(self) -> None:
        """Ollama returns empty list when unreachable (no fallback)."""
        with patch("app.infrastructure.providers.model_list._fetch_ollama", return_value=None):
            models = await fetch_models("ollama")
        assert models == []

    @pytest.mark.asyncio
    async def test_ollama_with_models(self) -> None:
        with patch("app.infrastructure.providers.model_list._fetch_ollama", return_value=["ollama/llama3"]):
            models = await fetch_models("ollama")
        assert "ollama/llama3" in models

    @pytest.mark.asyncio
    async def test_openaicompatible_live(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAICOMPATIBLE_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("OPENAICOMPATIBLE_API_KEY", "key")

        with patch("app.infrastructure.providers.model_list._fetch_openaicompatible") as mock_fetch:
            mock_fetch.return_value = ["custom-model"]
            models = await fetch_models("openaicompatible")

        assert "custom-model" in models

    @pytest.mark.asyncio
    async def test_opencode_live(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENCODE_GO_API_KEY", "oc-key")

        models = await fetch_models("opencode")
        assert len(models) > 0
        # Should return the fallback list
        assert "deepseek-v4-pro" in models or "deepseek-v4-flash" in models

    @pytest.mark.asyncio
    async def test_force_refresh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """force_refresh=True bypasses cache and re-fetches."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with patch("app.infrastructure.providers.model_list._fetch_openai") as mock_fetch:
            mock_fetch.return_value = ["gpt-4o"]
            await fetch_models("openai")
            assert mock_fetch.call_count == 1

            # Second call without force_refresh uses cache
            await fetch_models("openai")
            assert mock_fetch.call_count == 1  # still 1 — used cache

            # force_refresh re-fetches
            await fetch_models("openai", force_refresh=True)
            assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_live_result_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When live fetch returns empty list, use fallbacks."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with patch("app.infrastructure.providers.model_list._fetch_openai", return_value=[]):
            models = await fetch_models("openai")

        # Should fall back
        assert len(models) > 0
        assert "gpt-4o-mini" in models

    @pytest.mark.asyncio
    async def test_unknown_provider_fallback(self) -> None:
        """Unknown providers get empty fallback list."""
        models = await fetch_models("nonexistent_provider")
        assert models == []

    @pytest.mark.asyncio
    async def test_case_insensitive_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider name is normalized to lowercase."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with patch("app.infrastructure.providers.model_list._fetch_openai", return_value=["gpt-4o"]):
            models = await fetch_models("OpenAI")  # mixed case
        assert models == ["gpt-4o"]

    @pytest.mark.asyncio
    async def test_param_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit api_key parameter overrides env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")

        with patch("app.infrastructure.providers.model_list._fetch_openai") as mock_fetch:
            mock_fetch.return_value = ["gpt-4o"]
            await fetch_models("openai", api_key="param-key")

        mock_fetch.assert_called_once_with("param-key")


# ── HTTP fetch functions with mocked httpx ────────────────────────────


class TestFetchOpenAI:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """_fetch_openai parses the OpenAI /v1/models response correctly."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"id": "gpt-4o", "owned_by": "openai"},
                {"id": "gpt-4o-mini", "owned_by": "openai"},
            ]
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_openai("sk-test")

        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models
        mock_client.get.assert_called_once_with(
            "https://api.openai.com/v1/models",
            headers={"Authorization": "Bearer sk-test"},
        )

    @pytest.mark.asyncio
    async def test_fetch_filters_empty_ids(self) -> None:
        """Empty or missing IDs are excluded from the result."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"id": "gpt-4o"},
                {"id": ""},  # empty — should be excluded
                {},  # no id — should be excluded
                {"id": "gpt-4o-mini"},
            ]
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_openai("sk-test")

        assert models == ["gpt-4o", "gpt-4o-mini"]


class TestFetchAnthropic:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """_fetch_anthropic parses the Anthropic /v1/models response correctly."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"id": "claude-sonnet-4-20250514"},
                {"id": "claude-opus-4-20250514"},
            ]
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_anthropic("ant-key")

        assert "claude-sonnet-4-20250514" in models
        mock_client.get.assert_called_once_with(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": "ant-key", "anthropic-version": "2023-06-01"},
        )


class TestFetchGemini:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """_fetch_gemini parses the Gemini response with model name transformation."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.5-flash",
                    "supportedGenerationMethods": ["generateContent", "countTokens"],
                },
                {
                    "name": "models/gemini-2.5-pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/embedding-001",
                    "supportedGenerationMethods": ["embedContent"],  # not generateContent
                },
            ]
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_gemini("gem-key")

        assert "gemini/gemini-2.5-flash" in models
        assert "gemini/gemini-2.5-pro" in models
        # embedding model should be excluded
        assert "gemini/embedding-001" not in models
        mock_client.get.assert_called_once_with(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": "gem-key"},
        )

    @pytest.mark.asyncio
    async def test_fetch_skips_non_models_prefix(self) -> None:
        """Models without 'models/' prefix are skipped."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "tunedModels/my-model", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_gemini("gem-key")

        assert models == ["gemini/gemini-2.0-flash"]


class TestFetchOllama:
    @pytest.mark.asyncio
    async def test_fetch_via_http_success(self) -> None:
        """_fetch_ollama returns models from /api/tags endpoint."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama3:latest"},
                {"name": "mistral:7b"},
            ]
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_ollama("http://localhost:11434")

        assert "ollama/llama3:latest" in models
        assert "ollama/mistral:7b" in models

    @pytest.mark.asyncio
    async def test_fetch_http_error_falls_back(self) -> None:
        """When HTTP fails, _fetch_ollama falls back to CLI or returns None."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=RuntimeError("connection refused"))

        # Also mock subprocess to fail
        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            with patch("app.infrastructure.providers.model_list.asyncio.to_thread", side_effect=RuntimeError("no CLI")):
                result = await _fetch_ollama("http://localhost:11434")

        assert result is None  # unreachable

    @pytest.mark.asyncio
    async def test_fetch_cli_fallback_success(self) -> None:
        """When HTTP fails but CLI succeeds, models are returned."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=RuntimeError("connection refused"))

        async def _fake_to_thread(fn, *args, **kwargs):
            # Return a mock subprocess result
            result = MagicMock()
            result.returncode = 0
            result.stdout = "NAME\nllama3:latest\nmistral:7b\n"
            return result

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            with patch("app.infrastructure.providers.model_list.asyncio.to_thread", side_effect=_fake_to_thread):
                result = await _fetch_ollama("http://localhost:11434")

        assert result is not None
        assert "ollama/llama3:latest" in result
        assert "ollama/mistral:7b" in result

    @pytest.mark.asyncio
    async def test_fetch_cli_nonzero_exit(self) -> None:
        """When CLI returns non-zero exit code, result is None."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=RuntimeError("connection refused"))

        async def _fake_to_thread(fn, *args, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stdout = ""
            return result

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            with patch("app.infrastructure.providers.model_list.asyncio.to_thread", side_effect=_fake_to_thread):
                result = await _fetch_ollama("http://localhost:11434")

        assert result is None


class TestFetchOpenAICompatible:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """_fetch_openaicompatible fetches from a compatible endpoint."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"id": "custom-model-v1"},
                {"id": "custom-model-v2"},
            ]
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_openaicompatible("https://api.example.com/v1", "key123")

        assert "custom-model-v1" in models
        assert "custom-model-v2" in models
        mock_client.get.assert_called_once_with(
            "https://api.example.com/v1/models",
            headers={"Authorization": "Bearer key123"},
        )

    @pytest.mark.asyncio
    async def test_fetch_no_api_key(self) -> None:
        """When no API key is provided, no Authorization header is sent."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"id": "model-x"}]}
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("app.infrastructure.providers.model_list.httpx.AsyncClient", return_value=mock_client):
            models = await _fetch_openaicompatible("https://api.example.com/v1", "")

        assert "model-x" in models
        # No Authorization header in call
        call_args = mock_client.get.call_args
        assert "Authorization" not in call_args[1]["headers"]

    @pytest.mark.asyncio
    async def test_fetch_empty_base_url(self) -> None:
        """When base_url is empty, returns empty list immediately."""
        # No httpx needed — returns [] before any network call
        models = await _fetch_openaicompatible("", "")
        assert models == []

