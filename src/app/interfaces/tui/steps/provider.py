"""Step 1: Provider selection — choose translation service, credentials, and model.

Shows/hides API key, endpoint, and model fields based on the selected provider.
Checks environment variables to indicate whether a key is already configured.
Fetches live model lists from each provider's API in the background (fallback
to hardcoded list while loading or on error).
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import ClassVar

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Select

from ....infrastructure.providers.model_list import (
    FALLBACK_MODELS,
    fetch_models,
    get_cached_models,
)
from ..i18n import get_locale_from_app, t
from . import StepBack, StepComplete

# Auto-save to movamc.toml
try:
    from ....core.config_loader import save_config as _save_config
    from ....core.config_loader import settings_to_config_dict

    _HAS_SAVE_CONFIG = True
except ImportError:
    _HAS_SAVE_CONFIG = False

_CUSTOM = "__custom__"
"""Select value used for the 'Custom…' option — switches to free-text Input."""

_MASKED_KEY = "********************"
"""Displayed in the API key field when a key is already loaded from .env."""


class ProviderStep(Widget):
    """Select translation provider and configure credentials."""

    _PROVIDER_IDS: ClassVar[dict[str, str]] = {
        "prov-google": "google",
        "prov-openai": "openai",
        "prov-anthropic": "anthropic",
        "prov-gemini": "gemini",
        "prov-ollama": "ollama",
        "prov-openaicompatible": "openaicompatible",
        "prov-opencode": "opencode",
    }

    _ENV_VARS: ClassVar[dict[str, str]] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openaicompatible": "OPENAICOMPATIBLE_API_KEY",
        "opencode": "OPENCODE_GO_API_KEY",
    }

    _ENDPOINT_DEFAULTS: ClassVar[dict[str, tuple[str, str]]] = {
        "ollama": ("OLLAMA_API_BASE", "http://localhost:11434"),
        "openaicompatible": ("OPENAICOMPATIBLE_BASE_URL", "http://localhost:8080/v1"),
    }

    # Injected by wizard controller from saved config
    initial_provider: str = "google"
    initial_model: str = ""
    _cfg_save_debounce: Timer | None = None

    DEFAULT_CSS = """
    ProviderStep > RadioSet { margin: 0 0 2 0; }
    ProviderStep > .cred-field { margin: 0 0 1 0; max-width: 60; }
    ProviderStep > .cred-field.hidden { display: none; }
    ProviderStep > #cred-header { margin: 0; text-style: bold; color: $text-muted; }
    ProviderStep > #no-cred-note { margin: 0 0 1 0; color: $success; }
    ProviderStep > #env-indicator { margin: 0 0 1 0; color: $warning; }
    ProviderStep > #model-container { margin: 0 0 1 0; }
    ProviderStep > #model-label { margin: 0; }
    ProviderStep > #model-container > Select { margin: 0; }
    ProviderStep > #model-container > Input { margin: 0; }
    ProviderStep > #endpoint-label { margin: 0; }
    ProviderStep > #provider-error { color: $error; text-style: bold; margin: 0 0 1 0; }
    ProviderStep > #model-loading { color: $text-muted; text-style: italic; margin: 0 0 1 0; }
    """

    def compose(self) -> ComposeResult:
        locale = get_locale_from_app(self.app)
        yield Label(t("provider.title", locale), classes="step-title")
        yield RadioSet(
            RadioButton(t("provider.radio.google", locale), value=True, id="prov-google"),
            RadioButton(t("provider.radio.openai", locale), id="prov-openai"),
            RadioButton(t("provider.radio.anthropic", locale), id="prov-anthropic"),
            RadioButton(t("provider.radio.gemini", locale), id="prov-gemini"),
            RadioButton(t("provider.radio.ollama", locale), id="prov-ollama"),
            RadioButton(t("provider.radio.openaicompatible", locale), id="prov-openaicompatible"),
            RadioButton(t("provider.radio.opencode", locale), id="prov-opencode"),
            id="provider-radio",
        )
        yield Label(t("provider.credentials", locale), id="cred-header")
        yield Input(
            placeholder=t("provider.api_placeholder", locale),
            id="api-input",
            classes="cred-field",
        )
        yield Label(t("provider.base_url", locale), id="endpoint-label")
        yield Input(
            placeholder=t("provider.base_url", locale),
            id="endpoint-input",
            classes="cred-field",
        )
        yield Label(t("provider.model", locale), id="model-label")
        with Container(id="model-container"):
            yield Select(
                options=[],
                id="model-select",
            )
            yield Input(
                placeholder=t("provider.model_custom", locale),
                id="model-custom-input",
                classes="cred-field",
            )
        yield Label("", id="model-loading")
        yield Label(t("provider.no_cred", locale), id="no-cred-note")
        yield Label("", id="env-indicator")
        yield Label("", id="provider-error")
        yield Horizontal(
            Button(t("nav.back", locale), id="back-btn"),
            Button(t("nav.next", locale), id="next-btn", variant="primary"),
            id="nav-row",
        )

    def apply_locale(self) -> None:
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        self.query_one(".step-title", Label).update(t("provider.title", locale))
        radio_labels = {
            "prov-google": "provider.radio.google",
            "prov-openai": "provider.radio.openai",
            "prov-anthropic": "provider.radio.anthropic",
            "prov-gemini": "provider.radio.gemini",
            "prov-ollama": "provider.radio.ollama",
            "prov-openaicompatible": "provider.radio.openaicompatible",
            "prov-opencode": "provider.radio.opencode",
        }
        for btn in self.query(RadioButton):
            if btn.id in radio_labels:
                btn.label = t(radio_labels[btn.id], locale)
        self.query_one("#cred-header", Label).update(t("provider.credentials", locale))
        self.query_one("#endpoint-label", Label).update(t("provider.base_url", locale))
        self.query_one("#model-label", Label).update(t("provider.model", locale))
        self.query_one("#no-cred-note", Label).update(t("provider.no_cred", locale))
        self.query_one("#back-btn", Button).label = t("nav.back", locale)
        self.query_one("#next-btn", Button).label = t("nav.next", locale)

    def _has_api_key(self, provider: str) -> bool:
        if provider not in self._ENV_VARS:
            return True
        api_val = self.query_one("#api-input", Input).value
        if api_val and api_val != _MASKED_KEY:
            return True
        return self._check_env_key(provider) is not None

    def on_mount(self) -> None:
        """Select saved provider from config, if any."""
        self._suppress_save = True
        self.call_after_refresh(self._init_provider_fields)
        self.set_timer(0.3, self._enable_save)

    def _init_provider_fields(self) -> None:
        for btn in self.query(RadioButton):
            pid = btn.id or ""
            if self._PROVIDER_IDS.get(pid) == self.initial_provider:
                btn.value = True
                break
        self._update_fields(self.initial_provider)
        if self.initial_provider != "google":
            self._refresh_models_bg(self.initial_provider)

    def _enable_save(self) -> None:
        self._suppress_save = False

    # ── Helpers ────────────────────────────────────────────────────

    def _get_provider(self) -> str:
        radio = self.query_one("#provider-radio", RadioSet)
        pressed = radio.pressed_button
        if pressed is None or pressed.id is None:
            return "google"
        return self._PROVIDER_IDS.get(pressed.id, "google")

    def _check_env_key(self, provider: str) -> str | None:
        """Return the env var value for this provider's API key, if set."""
        env_var = self._ENV_VARS.get(provider)
        if env_var:
            val = os.getenv(env_var)
            if val and not val.startswith("your_") and val != "":
                return val
        return None

    def _build_model_options(self, provider: str, live_models: list[str] | None = None) -> list[tuple[str, str]]:
        """Build model Select options for *provider*, ending with Custom…."""
        if live_models is not None:
            models = live_models
        elif provider == "ollama":
            # Ollama: never show fallback, only live-fetched models or empty
            models = []
        else:
            models = FALLBACK_MODELS.get(provider, [])
        options = [(m, m) for m in models]
        try:
            locale = get_locale_from_app(self.app)
        except Exception:
            locale = "en"
        options.append((t("provider.custom", locale), _CUSTOM))
        return options

    def _is_custom_model(self) -> bool:
        """True when the user has selected Custom… in the model Select."""
        sel = self.query_one("#model-select", Select)
        return sel.value == _CUSTOM

    def _get_model(self) -> str | None:
        """Return the currently chosen model, or None if unset / loading."""
        if self._is_custom_model():
            val = self.query_one("#model-custom-input", Input).value
            return val.strip() if val and val.strip() else None
        sel = self.query_one("#model-select", Select)
        if sel.value and sel.value not in (_CUSTOM, "__loading__", "__failed__"):
            return str(sel.value)
        return None

    # ── Field visibility ───────────────────────────────────────────

    def _update_fields(self, provider: str) -> None:
        """Show/hide/enable credential fields based on the selected provider."""
        if not self.is_mounted:
            return
        api_input = self.query_one("#api-input", Input)
        endpoint_input = self.query_one("#endpoint-input", Input)
        model_container = self.query_one("#model-container", Container)
        model_custom = self.query_one("#model-custom-input", Input)
        cred_header = self.query_one("#cred-header", Label)
        no_cred = self.query_one("#no-cred-note", Label)
        env_indicator = self.query_one("#env-indicator", Label)

        # Reset all
        api_input.display = False
        endpoint_input.display = False
        model_container.display = False
        model_custom.display = False
        cred_header.display = True
        no_cred.display = False
        env_indicator.update("")
        self.query_one("#endpoint-label", Label).display = False
        self.query_one("#model-label", Label).display = False

        if provider == "google":
            cred_header.display = False
            no_cred.display = True
            return

        cred_header.display = True
        needs_endpoint = provider in self._ENDPOINT_DEFAULTS

        # API Key field
        if provider in self._ENV_VARS:
            api_input.display = True
            locale = get_locale_from_app(self.app)
            env_key = self._check_env_key(provider)
            if env_key:
                api_input.value = _MASKED_KEY
                api_input.placeholder = t("provider.api_override", locale)
                env_indicator.update(t("provider.env_key", locale))
            else:
                api_input.value = ""
                api_input.placeholder = t("provider.api_paste", locale)
        else:
            api_input.display = False

        # Endpoint field
        if needs_endpoint:
            endpoint_input.display = True
            self.query_one("#endpoint-label", Label).display = True
            env_var, default_val = self._ENDPOINT_DEFAULTS[provider]
            env_val = os.getenv(env_var)
            endpoint_input.value = env_val if env_val else default_val
            endpoint_input.placeholder = default_val
        else:
            endpoint_input.display = False

        # Model selector — reuse session cache so locale/visibility refresh
        # does not wipe a previously fetched Ollama model list.
        cached = get_cached_models(provider)
        self._populate_model_select(provider, live_models=cached)
        model_container.display = True
        self.query_one("#model-label", Label).display = True

    def _populate_model_select(self, provider: str, live_models: list[str] | None = None) -> None:
        """Fill the model Select with options and restore saved value."""
        model_select = self.query_one("#model-select", Select)
        model_custom = self.query_one("#model-custom-input", Input)

        options = self._build_model_options(provider, live_models=live_models)
        model_select.set_options(options)

        # Try to restore the saved model (initial_model)
        saved = self.initial_model
        if saved:
            known_values = [v for _, v in options if v != _CUSTOM]
            if saved in known_values:
                model_select.value = saved
                model_custom.display = False
                return
            # Custom model — select Custom… and pre-fill the input
            model_select.value = _CUSTOM
            model_custom.value = saved
            model_custom.display = True
            return

        # No saved model — default to first known model
        first_known = next((v for _, v in options if v != _CUSTOM), _CUSTOM)
        model_select.value = first_known
        if first_known == _CUSTOM:
            model_custom.display = True
        else:
            model_custom.display = False

    # ── Live model fetching ────────────────────────────────────────

    def _refresh_models_bg(self, provider: str) -> None:
        """Fetch live models in background and update Select when done."""
        locale = get_locale_from_app(self.app)
        with contextlib.suppress(Exception):
            self.query_one("#model-loading", Label).update(t("provider.loading_models", locale))
        self.run_worker(self._fetch_and_update(provider), exclusive=True)

    def _fetch_credentials(self, provider: str) -> tuple[str | None, str | None]:
        """Return (api_key, base_url) from the current widget values."""
        api_val = self.query_one("#api-input", Input).value
        api_key = api_val if api_val and api_val != _MASKED_KEY else None
        endpoint_val = self.query_one("#endpoint-input", Input).value.strip()
        base_url = endpoint_val or None
        return api_key, base_url

    async def _fetch_and_update(self, provider: str) -> None:
        """Fetch models and replace Select options if still mounted."""
        try:
            api_key, base_url = self._fetch_credentials(provider)
            models = await fetch_models(
                provider,
                api_key=api_key,
                base_url=base_url,
                force_refresh=True,
            )
            logger.debug("[ProviderStep] _fetch_and_update({}) -> {} models", provider, len(models))
            if not self._can_update_models():
                logger.debug("[ProviderStep] Widget not mounted, skipping")
                return
            if models:
                logger.debug("[ProviderStep] Updating select with {}", models)
                self._populate_model_select(provider, live_models=models)
        except Exception:
            logger.exception("_fetch_and_update failed")
        finally:
            with contextlib.suppress(Exception):
                self.query_one("#model-loading", Label).update("")

    def _can_update_models(self) -> bool:
        """Check whether this widget is still attached to the DOM."""
        try:
            return self.is_mounted and self.query_one("#model-select", Select) is not None
        except Exception:
            return False

    # ── Event handlers ─────────────────────────────────────────────

    def on_widget_focused(self, event: Widget.Focused) -> None:  # type: ignore[name-defined]
        """Clear the masked placeholder when user focuses the API key field."""
        widget = event.widget
        if isinstance(widget, Input) and widget.id == "api-input" and widget.value == _MASKED_KEY:
            widget.value = ""

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        pid = event.pressed.id if event.pressed else ""
        provider = self._PROVIDER_IDS.get(pid or "", "google")
        self._update_fields(provider)
        if provider != "google":
            self._refresh_models_bg(provider)
        self._debounce_auto_save_config()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Show/hide custom model Input when Custom… is selected. Also auto-saves."""
        if event.select.id == "model-select":
            model_custom = self.query_one("#model-custom-input", Input)
            if event.value == _CUSTOM:
                model_custom.display = True
                model_custom.focus()
            else:
                model_custom.display = False
                model_custom.value = ""
            self._auto_save_config()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next-btn":
            locale = get_locale_from_app(self.app)
            provider = self._get_provider()
            error = self.query_one("#provider-error", Label)
            error.update("")

            if provider != "google":
                if provider in self._ENV_VARS and not self._has_api_key(provider):
                    error.update(t("provider.error_no_key", locale))
                    return
                model_val = self._get_model()
                if not model_val:
                    error.update(t("provider.error_no_model", locale))
                    return

            data: dict = {"provider": provider}
            api_val = self.query_one("#api-input", Input).value
            if api_val and api_val != _MASKED_KEY:
                data["api_key"] = api_val

            endpoint_val = self.query_one("#endpoint-input", Input).value
            if endpoint_val:
                data["endpoint"] = endpoint_val

            model_val = self._get_model()
            if model_val:
                data["model"] = model_val

            self._save_env(provider, api_val, endpoint_val)
            self.post_message(StepComplete(data))
        elif event.button.id == "back-btn":
            self.post_message(StepBack())

    # ── .env management ────────────────────────────────────────────

    _ENV_KEY_MAP: ClassVar[dict[str, str]] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openaicompatible": "OPENAICOMPATIBLE_API_KEY",
        "opencode": "OPENCODE_GO_API_KEY",
    }
    _ENDPOINT_ENV_MAP: ClassVar[dict[str, str]] = {
        "ollama": "OLLAMA_API_BASE",
        "openaicompatible": "OPENAICOMPATIBLE_BASE_URL",
    }

    def _save_env(self, provider: str, api_key: str | None, endpoint: str | None) -> None:
        """Write API key and endpoint for *provider* to .env file.

        Uses python-dotenv if available; falls back to manual line-based
        editing when the package is not installed.
        """
        if provider == "google":
            return

        env_path = Path(".env")
        updates: dict[str, str] = {}

        # API key
        key_var = self._ENV_KEY_MAP.get(provider)
        if key_var and api_key and api_key != _MASKED_KEY:
            updates[key_var] = api_key

        # Endpoint / base URL
        url_var = self._ENDPOINT_ENV_MAP.get(provider)
        if url_var and endpoint:
            updates[url_var] = endpoint

        if not updates:
            return

        try:
            from dotenv import set_key

            for var, val in updates.items():
                set_key(str(env_path), var, val, quote_mode="always")
        except ImportError:
            self._save_env_manual(env_path, updates)

        locale = get_locale_from_app(self.app)
        self.app.notify(  # type: ignore[attr-defined]
            t("notify.credentials_saved", locale, name=env_path.name),
            timeout=3,
        )

    def _save_env_manual(self, env_path: Path, updates: dict[str, str]) -> None:
        """Fallback: update .env without python-dotenv."""
        lines: list[str] = []
        updated: set[str] = set()

        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()

        for i, line in enumerate(lines):
            stripped = line.strip()
            for var in updates:
                if stripped.startswith(f"{var}=") or stripped.startswith(f"# {var}="):
                    lines[i] = f'{var}="{updates[var]}"'
                    updated.add(var)

        for var, val in updates.items():
            if var not in updated:
                lines.append(f'{var}="{val}"')

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ── Auto-save to movamc.toml ──────────────────────────────

    def _auto_save_config(self) -> None:
        """Save current provider + model to movamc.toml when changed."""
        if getattr(self, "_suppress_save", False) or not _HAS_SAVE_CONFIG:
            return
        try:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            settings = wiz.settings

            data = settings_to_config_dict(settings, ui_locale=wiz.ui_locale)
            data["provider"] = self._get_provider()
            data["model"] = self._get_model() or settings.model
            saved = _save_config(data, wiz.config_path)
            if not wiz.config_path:
                wiz.config_path = saved
        except Exception:
            logger.exception("[ProviderStep] auto-save failed")

    def _debounce_auto_save_config(self) -> None:
        """Debounce config saves — don't write TOML on rapid radio clicks."""
        try:
            if self._cfg_save_debounce is not None:
                self._cfg_save_debounce.cancel()  # type: ignore[attr-defined]
        except (AttributeError, ReferenceError):
            pass
        self._cfg_save_debounce = self.set_timer(0.3, self._auto_save_config)
