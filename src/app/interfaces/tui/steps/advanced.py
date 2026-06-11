"""Step 3: Advanced settings — cache, workers, hint language, dry-run, glossary.

Values are auto-saved to movamc.toml on every change (no save button needed).

"""

from __future__ import annotations

import contextlib
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, HorizontalGroup
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Collapsible, Input, Label, Select, Switch

from ....core.config_loader import save_config, settings_to_config_dict
from ....domain.languages import LANGUAGE_NAMES
from ....infrastructure.providers.model_list import FALLBACK_MODELS
from ..i18n import get_locale_from_app, t
from . import StepBack, StepComplete

_LANGUAGE_OPTIONS_CACHE: list[tuple[str, str]] | None = None

_SELECT_SENTINELS = frozenset({"Select.NULL", "Select.BLANK"})

_QA_CUSTOM = "__qa_custom__"

"""Select sentinel for the 'Custom…' option in QA model selector."""

_QA_PROVIDER_OPTIONS: list[tuple[str, str]] = [
    ("Same as translator", ""),
    ("OpenAI", "openai"),
    ("Anthropic", "anthropic"),
    ("Google Gemini", "gemini"),
    ("Ollama (local)", "ollama"),
    ("OpenAI-Compatible", "openaicompatible"),
    ("OpenCode Go", "opencode"),
]


def _clean_select_value(val: str | None) -> str | None:
    """Coerce Select sentinel values (e.g. 'Select.NULL') to None.

    Textual's Select widget may leak internal sentinels into saved config

    if an undefined or blank value round-trips through save then load.

    Empty strings are also treated as None (not a valid model name).

    """

    if not val or val in _SELECT_SENTINELS:
        return None

    return val


def _parse_optional_int(val: str) -> int | None:

    val = val.strip()

    if not val:
        return None

    try:
        return int(val)

    except ValueError:
        return None


def _parse_required_int(val: str, default: int) -> int | None:

    val = val.strip()

    if not val:
        return default

    try:
        return int(val)

    except ValueError:
        return None


def _parse_optional_float(val: str) -> float | None:

    val = val.strip()

    if not val:
        return None

    return float(val)


def _language_options() -> list[tuple[str, str]]:
    """Return sorted list of (display_name, code) for Select widget.

    Cached after first call to avoid re-sorting 150+ entries on every

    step mount.

    """

    global _LANGUAGE_OPTIONS_CACHE

    if _LANGUAGE_OPTIONS_CACHE is None:
        _LANGUAGE_OPTIONS_CACHE = sorted(
            ((f"{name}", code) for code, name in LANGUAGE_NAMES.items()),
            key=lambda x: x[0].lower(),
        )

    return _LANGUAGE_OPTIONS_CACHE


class AdvancedStep(Widget):
    """Configure advanced translation options."""

    # Injected by wizard controller

    initial_no_cache: bool = False

    initial_workers: int = 4

    initial_hint_lang: str | None = None

    initial_dry_run: bool = False
    _save_debounce_timer: Timer | None = None

    initial_glossary_path: str = ""

    initial_output_mode: str = "separate"

    initial_qa_judge: bool = False

    initial_qa_judge_provider: str = ""

    initial_qa_judge_model: str = ""

    initial_qa_threshold: int = 3

    initial_qa_max_attempts: int = 2

    initial_qa_streaming: bool = True

    initial_qa_chunk_size: int = 25

    initial_qa_judge_workers: int = 2

    initial_chunk_mode: str = "auto"

    initial_chunk_size: int | None = None

    initial_progress_batch_size: int = 10

    initial_rate_limit_rpm: float | None = None

    initial_rate_limit_burst: float | None = None

    initial_judge_rpm: float | None = None

    initial_judge_burst: float | None = None

    DEFAULT_CSS = """

    AdvancedStep {

        height: auto;

        width: 100%;

    }

    AdvancedStep > #adv-hint { color: $text-muted; text-style: italic; margin: 0 0 1 0; height: auto; }

    /* Toggle switches — 2x2 grid */

    AdvancedStep .toggle-row { height: 3; margin: 0 0 1 0; width: 100%; }

    AdvancedStep .toggle-row > .toggle-cell { width: 1fr; height: 3; align: left middle; }

    AdvancedStep .toggle-row > .toggle-cell > Switch { margin: 0; }

    AdvancedStep .toggle-row > .toggle-cell > Label { margin: 0 0 0 1; }

    /* Inline field: label + input on one row */

    AdvancedStep .inline-field { height: 3; margin: 0 0 1 0; width: 100%; }

    AdvancedStep .inline-field > Label { width: auto; padding: 0 1 0 0; content-align: left middle; }

    AdvancedStep .inline-field > Input { width: 1fr; }

    /* Side-by-side mini fields */

    AdvancedStep .mini-row { height: 3; margin: 0 0 1 0; width: 100%; }

    AdvancedStep .mini-row > .mini-cell { width: 1fr; height: 3; align: left middle; }

    AdvancedStep .mini-row > .mini-cell > Label {
        width: auto; padding: 0 1 0 0; content-align: left middle;
        color: $text;
    }

    AdvancedStep .mini-row > .mini-cell > Input { width: 1fr; margin: 0; }

    /* Regular fields */

    AdvancedStep .field-label { text-style: bold; color: $text; margin: 0 0 1 0; height: 1; }

    AdvancedStep .field-label-sm { text-style: bold; color: $text; margin: 0; height: 1; }

    AdvancedStep Select { margin: 0 0 1 0; height: auto; width: 100%; max-width: 60; }
    AdvancedStep Select > SelectCurrent { height: 3; width: 100%; }
    AdvancedStep Select > SelectCurrent.-has-value Static#label { color: $foreground; }
    AdvancedStep Input {
        margin: 0;
        height: 3;
        color: $foreground;
        background: $surface;
        padding: 0 1;
    }
    AdvancedStep Input > .input--placeholder { color: $text-muted; }
    AdvancedStep Container { height: auto; width: 100%; }

    AdvancedStep > #save-indicator { color: $success; text-style: italic; margin: 0 0 1 0; height: 1; }

    /* QA section — progressive disclosure */

    AdvancedStep > #qa-section { height: auto; width: 100%; margin: 0 0 1 0; }

    AdvancedStep > #qa-section > #qa-provider-label { margin: 0 0 1 0; height: 1; }

    AdvancedStep > #qa-section > #qa-model-label { margin: 0 0 1 0; height: 1; }

    AdvancedStep > #qa-section > #qa-model-container { height: auto; margin: 0 0 1 0; width: 100%; }

    AdvancedStep > #qa-section > #qa-model-container > Select { margin: 0 0 1 0; height: auto; }

    AdvancedStep > #qa-section > #qa-model-container > Input {
        margin: 0;
        height: 3;
        color: $foreground;
    }

    AdvancedStep > #qa-section > #qa-same-info {

        margin: 0 0 1 0; color: $text-muted; text-style: italic; height: auto;

    }

    AdvancedStep > #qa-section > .qa-toggle-row { height: 3; margin: 0 0 1 0; align: left middle; }

    AdvancedStep > #qa-section > .qa-toggle-row > Switch { margin: 0; }

    AdvancedStep > #qa-section > .qa-toggle-row > Label { margin: 0 0 0 1; }

    AdvancedStep > #perf-collapsible { margin: 0 0 1 0; height: auto; width: 100%; }

    AdvancedStep > #nav-row { height: auto; margin: 2 0 0 0; }

    AdvancedStep > #replace-warning { color: $warning; text-style: bold; margin: 0 0 1 0; }

    AdvancedStep > #advanced-error { color: $error; text-style: bold; margin: 0 0 1 0; }

    AdvancedStep .toggle-desc { color: $text-muted; text-style: italic; margin: 0 0 0 1; }

    """

    def compose(self) -> ComposeResult:

        locale = get_locale_from_app(self.app)

        yield Label(t("advanced.title", locale), classes="step-title")

        yield Label(t("advanced.hint", locale), id="adv-hint")

        # Toggle switches — 2x2 grid

        yield HorizontalGroup(
            HorizontalGroup(
                Switch(value=self.initial_no_cache, id="no-cache-switch"),
                Label(t("advanced.no_cache", locale), id="no-cache-label"),
                Label(t("advanced.no_cache_desc", locale), classes="toggle-desc", id="no-cache-desc"),
                classes="toggle-cell",
            ),
            classes="toggle-row",
            id="toggle-row-1",
        )

        yield HorizontalGroup(
            HorizontalGroup(
                Switch(value=self.initial_dry_run, id="dry-run-switch"),
                Label(t("advanced.dry_run", locale), id="dry-run-label"),
                Label(t("advanced.dry_run_desc", locale), classes="toggle-desc", id="dry-run-desc"),
                classes="toggle-cell",
            ),
            HorizontalGroup(
                Switch(value=self.initial_qa_judge, id="qa-judge-switch"),
                Label(t("advanced.qa_judge", locale), id="qa-judge-label"),
                Label(t("advanced.qa_judge_desc", locale), classes="toggle-desc", id="qa-judge-desc"),
                classes="toggle-cell",
            ),
            classes="toggle-row",
            id="toggle-row-2",
        )

        # Workers inline

        yield HorizontalGroup(
            Label(t("advanced.workers", locale), classes="field-label-sm", id="workers-label"),
            Input(
                value=str(self.initial_workers),
                placeholder="4",
                id="workers-input",
                type="integer",
            ),
            classes="inline-field",
        )

        # Hint language

        yield Label(t("advanced.hint_lang", locale), classes="field-label", id="hint-lang-label")

        opts = [(t("advanced.hint_none", locale), "")] + _language_options()

        yield Select(
            opts,
            prompt=t("advanced.hint_prompt", locale),
            value=self.initial_hint_lang or "",
            id="hint-lang-select",
            allow_blank=True,
        )

        # Glossary path

        yield HorizontalGroup(
            Label(t("advanced.glossary", locale), classes="field-label-sm", id="glossary-label"),
            Input(
                value=self.initial_glossary_path,
                placeholder=t("advanced.glossary_placeholder", locale),
                id="glossary-input",
            ),
            classes="inline-field",
        )

        # Output mode

        yield Label(t("advanced.output_mode", locale), classes="field-label", id="output-mode-label")

        yield Select(
            [
                (t("advanced.output_replace", locale), "replace"),
                (t("advanced.output_separate", locale), "separate"),
            ],
            value=self.initial_output_mode,
            id="output-mode-select",
        )

        yield Label(t("advanced.replace_warning", locale), id="replace-warning")

        # ── QA section (shown when QA judge is on) ──

        with Container(id="qa-section"):
            yield Label("QA Provider:", classes="field-label", id="qa-provider-label")

            yield Select(
                _QA_PROVIDER_OPTIONS,
                value=self.initial_qa_judge_provider or "",
                id="qa-provider-select",
            )

            yield Label("QA Model:", classes="field-label", id="qa-model-label")

            yield Label("", id="qa-same-info")

            yield HorizontalGroup(
                Switch(value=self.initial_qa_streaming, id="qa-streaming-switch"),
                Label("Inline QA during translate"),
                classes="qa-toggle-row",
            )

            with Container(id="qa-model-container"):
                yield Select(options=[], id="qa-model-select")

                yield Input(
                    placeholder="Type custom model name",
                    id="qa-model-custom-input",
                )

            yield HorizontalGroup(
                HorizontalGroup(
                    Label("Threshold:"),
                    Input(
                        value=str(self.initial_qa_threshold),
                        placeholder="3",
                        id="qa-threshold-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                HorizontalGroup(
                    Label("Max retries:"),
                    Input(
                        value=str(self.initial_qa_max_attempts),
                        placeholder="2",
                        id="qa-attempts-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                classes="mini-row",
            )

            yield HorizontalGroup(
                HorizontalGroup(
                    Label("QA chunk:"),
                    Input(
                        value=str(self.initial_qa_chunk_size),
                        placeholder="25",
                        id="qa-chunk-size-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                HorizontalGroup(
                    Label("Judge workers:"),
                    Input(
                        value=str(self.initial_qa_judge_workers),
                        placeholder="2",
                        id="qa-judge-workers-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                classes="mini-row",
            )

            yield Label("Judge rate limit (empty = global):", classes="field-label")

            yield HorizontalGroup(
                HorizontalGroup(
                    Label("Judge RPM:"),
                    Input(
                        value=str(int(self.initial_judge_rpm)) if self.initial_judge_rpm is not None else "",
                        placeholder="global",
                        id="judge-rpm-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                HorizontalGroup(
                    Label("Judge burst:"),
                    Input(
                        value=str(int(self.initial_judge_burst)) if self.initial_judge_burst is not None else "",
                        placeholder="global",
                        id="judge-burst-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                classes="mini-row",
            )

        # ── Performance tuning (collapsed by default) ──

        with Collapsible(title="Performance tuning", collapsed=True, id="perf-collapsible"):
            yield Label("Translation batching:", classes="field-label")

            yield Select(
                [
                    ("Auto (batch + parallel workers)", "auto"),
                    ("Fixed chunk size", "chunk"),
                    ("One item per request (live TUI)", "item"),
                ],
                value=self.initial_chunk_mode,
                id="chunk-mode-select",
            )

            yield HorizontalGroup(
                Label("Chunk size:", classes="field-label-sm"),
                Input(
                    value=str(self.initial_chunk_size) if self.initial_chunk_size is not None else "",
                    placeholder="25",
                    id="chunk-size-input",
                    type="integer",
                ),
                classes="inline-field",
                id="chunk-size-row",
            )

            yield HorizontalGroup(
                Label("Progress every N entries:", classes="field-label-sm"),
                Input(
                    value=str(self.initial_progress_batch_size),
                    placeholder="10",
                    id="progress-batch-input",
                    type="integer",
                ),
                classes="inline-field",
            )

            yield Label("Rate limit (empty = 60 RPM):", classes="field-label")

            yield HorizontalGroup(
                HorizontalGroup(
                    Label("RPM:"),
                    Input(
                        value=str(int(self.initial_rate_limit_rpm)) if self.initial_rate_limit_rpm is not None else "",
                        placeholder="60",
                        id="rate-limit-rpm-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                HorizontalGroup(
                    Label("Burst:"),
                    Input(
                        value=str(int(self.initial_rate_limit_burst))
                        if self.initial_rate_limit_burst is not None
                        else "",
                        placeholder="10",
                        id="rate-limit-burst-input",
                        type="integer",
                    ),
                    classes="mini-cell",
                ),
                classes="mini-row",
            )

        yield Label("", id="save-indicator")

        yield Label("", id="advanced-error")

        yield HorizontalGroup(
            Button(t("nav.back", locale), id="back-btn"),
            Button(t("advanced.continue", locale), id="next-btn", variant="primary"),
            id="nav-row",
        )

    def on_mount(self) -> None:
        """Suppress the initial auto-save that would fire when defaults are set.

        Auto-save is enabled only when the wizard navigates to this step
        (via :meth:`refresh_on_show`), preventing premature saves that
        could overwrite user choices made on earlier steps.
        """

        self._suppress_save = True
        self.call_after_refresh(self._init_advanced_fields)

    def _init_advanced_fields(self) -> None:
        if not self.is_mounted:
            return
        with contextlib.suppress(Exception):
            self.query_one("#qa-model-custom-input", Input).display = False
        if not self.initial_qa_judge:
            self.query_one("#qa-section", Container).display = False
        else:
            self._populate_qa_model_select(self.initial_qa_judge_provider or "")
        self._update_chunk_size_visibility()
        self._update_replace_warning()

    def apply_locale(self) -> None:
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        self.query_one(".step-title", Label).update(t("advanced.title", locale))
        self.query_one("#adv-hint", Label).update(t("advanced.hint", locale))
        self.query_one("#no-cache-label", Label).update(t("advanced.no_cache", locale))
        self.query_one("#no-cache-desc", Label).update(t("advanced.no_cache_desc", locale))
        self.query_one("#dry-run-label", Label).update(t("advanced.dry_run", locale))
        self.query_one("#dry-run-desc", Label).update(t("advanced.dry_run_desc", locale))
        self.query_one("#qa-judge-label", Label).update(t("advanced.qa_judge", locale))
        self.query_one("#qa-judge-desc", Label).update(t("advanced.qa_judge_desc", locale))
        self.query_one("#workers-label", Label).update(t("advanced.workers", locale))
        self.query_one("#hint-lang-label", Label).update(t("advanced.hint_lang", locale))
        self.query_one("#glossary-label", Label).update(t("advanced.glossary", locale))
        self.query_one("#output-mode-label", Label).update(t("advanced.output_mode", locale))
        self.query_one("#replace-warning", Label).update(t("advanced.replace_warning", locale))
        self.query_one("#back-btn", Button).label = t("nav.back", locale)
        self.query_one("#next-btn", Button).label = t("advanced.continue", locale)
        self._update_replace_warning()

    def _update_replace_warning(self) -> None:
        mode = str(self.query_one("#output-mode-select", Select).value or "replace")
        warning = self.query_one("#replace-warning", Label)
        warning.display = mode == "replace"

    def refresh_on_show(self) -> None:
        """Refresh dynamic content when the wizard shows this step.

        Enables auto-save after the initial population is complete,
        ensuring that any subsequent user interactions are persisted.
        """

        if self.query_one("#qa-judge-switch", Switch).value:
            self.query_one("#qa-section", Container).display = True

            self._populate_qa_model_select(self._get_qa_provider())

        else:
            self.query_one("#qa-section", Container).display = False

        self._update_chunk_size_visibility()

        self._update_replace_warning()

        # Enable auto-save now that the step is visible and initial
        # values are populated.  Prior to this point, saves are
        # suppressed to prevent stale wizard-state data from
        # overwriting user choices made on earlier steps.
        self._suppress_save = False

    def _update_chunk_size_visibility(self) -> None:

        mode = str(self.query_one("#chunk-mode-select", Select).value or "auto")

        chunk_row = self.query_one("#chunk-size-row", HorizontalGroup)

        chunk_row.display = mode == "chunk"

    def _enable_save(self) -> None:

        self._suppress_save = False

    # ── QA provider/model helpers ──────────────────────────────────

    def _get_qa_provider(self) -> str:
        """Return the currently selected QA provider.

        Empty string means "same as translator"."""

        sel = self.query_one("#qa-provider-select", Select)

        return str(sel.value) if sel.value else ""

    def _qa_model_options(self, provider: str) -> list[tuple[str, str]]:
        """Build model Select options for *provider*, ending with Custom…."""

        models = FALLBACK_MODELS.get(provider, [])

        options = [(m, m) for m in models]

        options.append(("Custom…", _QA_CUSTOM))

        return options

    def _populate_qa_model_select(self, provider: str) -> None:
        """Fill QA model Select with options and restore saved value.

        When provider is empty ("same as translator"), show an info label

        instead of the model selector."""

        model_container = self.query_one("#qa-model-container", Container)

        model_same_info = self.query_one("#qa-same-info", Label)

        model_label = self.query_one("#qa-model-label", Label)

        if not provider:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]

            trans_provider = wiz.settings.provider or "google"

            trans_model = wiz.settings.model or "(default)"

            model_display = trans_model

            if model_display and model_display.startswith(f"{trans_provider}/"):
                model_display = model_display[len(trans_provider) + 1 :]

            model_same_info.update(
                f"Using: [bold]{trans_provider}[/] / [bold]{model_display}[/] (from translator settings)"
            )

            model_same_info.display = True

            model_container.display = False

            model_label.display = True

            return

        model_label.display = True

        model_same_info.display = False

        model_container.display = True

        model_select = self.query_one("#qa-model-select", Select)

        model_custom = self.query_one("#qa-model-custom-input", Input)

        options = self._qa_model_options(provider)

        model_select.set_options(options)

        saved = self.initial_qa_judge_model

        if saved:
            known = [v for _, v in options if v != _QA_CUSTOM]

            if saved in known:
                model_select.value = saved

                model_custom.display = False

                return

            model_select.value = _QA_CUSTOM

            model_custom.value = saved

            model_custom.display = True

            return

        first = next((v for _, v in options if v != _QA_CUSTOM), _QA_CUSTOM)

        model_select.value = first

        model_custom.display = first == _QA_CUSTOM

    def _get_qa_model(self) -> str | None:
        """Return the currently chosen QA model, or None if unset."""

        sel = self.query_one("#qa-model-select", Select)

        if sel.value == _QA_CUSTOM:
            val = self.query_one("#qa-model-custom-input", Input).value

            return val.strip() if val and val.strip() else None

        if sel.value and sel.value not in (_QA_CUSTOM,):
            return str(sel.value)

        return None

    # ── Event handlers (auto-save on change) ───────────────────────

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Progressive disclosure: hide/show QA fields based on QA judge toggle."""

        if event.switch.id == "qa-judge-switch":
            if event.value:
                self.refresh_on_show()

            else:
                self.query_one("#qa-section", Container).display = False

        self._auto_save()

    def on_input_changed(self, _event: Input.Changed) -> None:
        """Debounce auto-save — don't write TOML on every keystroke."""

        self._debounce_save()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle QA provider/model selection with Custom… option."""

        sid = event.select.id

        if sid == "qa-provider-select":
            provider = str(event.value) if event.value else ""

            self._populate_qa_model_select(provider)

        elif sid == "qa-model-select":
            model_custom = self.query_one("#qa-model-custom-input", Input)

            if event.value == _QA_CUSTOM:
                model_custom.display = True

                model_custom.focus()

            else:
                model_custom.display = False

                model_custom.value = ""

        elif sid == "chunk-mode-select":
            self._update_chunk_size_visibility()

        elif sid == "output-mode-select":
            self._update_replace_warning()

        self._auto_save()

    # ── Actions ────────────────────────────────────────────────────

    def _collect_step_values(self) -> dict:

        hint_val = self.query_one("#hint-lang-select", Select).value

        chunk_mode = str(self.query_one("#chunk-mode-select", Select).value or "auto")

        chunk_size_raw = self.query_one("#chunk-size-input", Input).value

        chunk_size = _parse_optional_int(chunk_size_raw) if chunk_mode == "chunk" else None

        rate_limit: dict[str, Any] = {}

        rpm = _parse_optional_float(self.query_one("#rate-limit-rpm-input", Input).value)

        burst = _parse_optional_float(self.query_one("#rate-limit-burst-input", Input).value)

        if rpm is not None:
            rate_limit["rpm"] = rpm

        if burst is not None:
            rate_limit["burst"] = burst

        judge_rpm = _parse_optional_float(self.query_one("#judge-rpm-input", Input).value)

        judge_burst = _parse_optional_float(self.query_one("#judge-burst-input", Input).value)

        if judge_rpm is not None or judge_burst is not None:
            judge_cfg: dict[str, float] = {}

            if judge_rpm is not None:
                judge_cfg["rpm"] = judge_rpm

            if judge_burst is not None:
                judge_cfg["burst"] = judge_burst

            rate_limit["judge"] = judge_cfg

        return {
            "no_cache": self.query_one("#no-cache-switch", Switch).value,
            "dry_run": self.query_one("#dry-run-switch", Switch).value,
            "workers": _parse_required_int(self.query_one("#workers-input", Input).value, 4),
            "hint_lang": _clean_select_value(str(hint_val)) if hint_val else None,
            "glossary_path": self.query_one("#glossary-input", Input).value or None,
            "output_mode": self.query_one("#output-mode-select", Select).value,
            "chunk_mode": chunk_mode,
            "chunk_size": chunk_size,
            "progress_batch_size": _parse_required_int(self.query_one("#progress-batch-input", Input).value, 10),
            "qa_judge": self.query_one("#qa-judge-switch", Switch).value,
            "qa_judge_provider": self._get_qa_provider(),
            "qa_judge_model": _clean_select_value(self._get_qa_model()),
            "qa_threshold": _parse_required_int(self.query_one("#qa-threshold-input", Input).value, 3),
            "qa_max_attempts": _parse_required_int(self.query_one("#qa-attempts-input", Input).value, 2),
            "qa_streaming": self.query_one("#qa-streaming-switch", Switch).value,
            "qa_chunk_size": _parse_required_int(self.query_one("#qa-chunk-size-input", Input).value, 25),
            "qa_judge_workers": _parse_required_int(self.query_one("#qa-judge-workers-input", Input).value, 2),
            **({"rate_limit": rate_limit} if rate_limit else {}),
        }

    def _validate_values(self) -> str | None:
        locale = get_locale_from_app(self.app)
        int_fields = [
            ("workers-input", t("advanced.workers", locale).rstrip(":")),
            ("progress-batch-input", "progress_batch_size"),
            ("qa-threshold-input", "qa_threshold"),
            ("qa-attempts-input", "qa_max_attempts"),
            ("qa-chunk-size-input", "qa_chunk_size"),
            ("qa-judge-workers-input", "qa_judge_workers"),
        ]
        for field_id, field_name in int_fields:
            raw = self.query_one(f"#{field_id}", Input).value.strip()
            if raw and _parse_required_int(raw, -1) is None:
                return t("advanced.error_int", locale, field=field_name)
        workers = _parse_required_int(self.query_one("#workers-input", Input).value, 4)
        if workers is None or workers < 1:
            return t("advanced.error_workers", locale)
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:

        if event.button.id == "next-btn":
            error = self.query_one("#advanced-error", Label)
            validation = self._validate_values()
            if validation:
                error.update(validation)
                return
            error.update("")
            self.post_message(StepComplete(self._collect_step_values()))

        elif event.button.id == "back-btn":
            self.post_message(StepBack())

    # ── Auto-save ──────────────────────────────────────────────────

    def _gather_all_data(self) -> dict:
        """Collect all settings (from wizard state + current step inputs)."""

        wiz = self.app.wizard_state  # type: ignore[attr-defined]

        data = settings_to_config_dict(wiz.settings, ui_locale=wiz.ui_locale)

        data.update(self._collect_step_values())

        return data

    def _auto_save(self) -> None:
        """Save current settings to movamc.toml after a value change."""

        if getattr(self, "_suppress_save", False):
            return

        try:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]

            config_path = wiz.config_path

            data = self._gather_all_data()

            saved = save_config(data, config_path)

            indicator = self.query_one("#save-indicator", Label)

            locale = get_locale_from_app(self.app)
            indicator.update(t("advanced.save_ok", locale, name=saved.name))

            self.set_timer(2.5, self._clear_save_indicator)

            if not wiz.config_path:
                wiz.config_path = saved

        except Exception as e:
            indicator = self.query_one("#save-indicator", Label)

            locale = get_locale_from_app(self.app)
            indicator.update(t("advanced.save_fail", locale, error=str(e)))

    def _debounce_save(self) -> None:
        """Reset timer on each keystroke — save fires 0.5s after typing stops."""

        try:
            if self._save_debounce_timer is not None:
                self._save_debounce_timer.cancel()  # type: ignore[attr-defined]

        except (AttributeError, ReferenceError):
            pass

        self._save_debounce_timer = self.set_timer(0.5, self._auto_save)

    def _clear_save_indicator(self) -> None:

        try:
            self.query_one("#save-indicator", Label).update("")

        except Exception:
            pass
