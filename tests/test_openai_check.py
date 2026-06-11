import os
from unittest.mock import MagicMock, patch

from app.core.provider_check import check_provider_available


class TestProviderCheck:
    def test_google_always_available(self):
        available, _msg = check_provider_available("google")
        assert available is True

    def test_openai_available_with_key(self):
        mock_litellm = MagicMock()
        with (
            patch.dict("sys.modules", {"litellm": mock_litellm}),
            patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}),
        ):
            available, _msg = check_provider_available("openai")
            assert available is True

    def test_openai_unavailable_no_key(self):
        mock_litellm = MagicMock()
        with patch.dict("sys.modules", {"litellm": mock_litellm}), patch.dict(os.environ, {}, clear=True):
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            available, _msg = check_provider_available("openai")
            assert available is False

    def test_anthropic_available_with_key(self):
        mock_litellm = MagicMock()
        with (
            patch.dict("sys.modules", {"litellm": mock_litellm}),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}),
        ):
            available, _msg = check_provider_available("anthropic")
            assert available is True

    def test_anthropic_unavailable_no_key(self):
        mock_litellm = MagicMock()
        with patch.dict("sys.modules", {"litellm": mock_litellm}), patch.dict(os.environ, {}, clear=True):
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]
            available, _msg = check_provider_available("anthropic")
            assert available is False

    def test_gemini_available_with_key(self):
        mock_litellm = MagicMock()
        with (
            patch.dict("sys.modules", {"litellm": mock_litellm}),
            patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-test-key"}),
        ):
            available, _msg = check_provider_available("gemini")
            assert available is True

    def test_gemini_unavailable_no_key(self):
        mock_litellm = MagicMock()
        with (
            patch.dict("sys.modules", {"litellm": mock_litellm}),
            patch.dict(os.environ, {}, clear=True),
            patch("app.infrastructure.providers.registry._try_load_dotenv"),
        ):
            available, _msg = check_provider_available("gemini")
            assert available is False

    def test_ollama_always_available(self):
        mock_litellm = MagicMock()
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            available, _msg = check_provider_available("ollama")
            assert available is True

    def test_litellm_always_available(self):
        mock_litellm = MagicMock()
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            available, _msg = check_provider_available("litellm")
            assert available is True

    def test_litellm_not_installed(self):
        import builtins

        with patch.dict(os.environ, {}, clear=True):
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]

            _orig = builtins.__import__

            def _blocked(name, *a, **kw):
                if name in ("openai", "litellm"):
                    raise ImportError(name)
                return _orig(name, *a, **kw)

            with patch("builtins.__import__", _blocked):
                available, _msg = check_provider_available("openai")
                assert available is False
                assert "not installed" in _msg

    def test_unknown_provider(self):
        available, _msg = check_provider_available("nonexistent")
        assert available is False
