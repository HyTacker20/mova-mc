"""Wizard screen — step-by-step navigation for translation workflow.

Owns a Stepper header, a StepCard body (cross-fade animated step widgets),
and a Footer keybar. Steps are Widgets (not Screens), swapped in/out of the card.

Step widgets are **pre-created and mounted** in ``compose()`` — navigating
only toggles ``display``, with zero DOM manipulation after startup.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ...application.pipeline import PipelineResult

from loguru import logger
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Footer, Label, ProgressBar

from ...core.config_loader import find_config_file, load_config
from ...core.mod_scanner import ModInfo, ModScanner
from ...core.settings import Settings
from ...domain.stats import OverallStats
from ...utils.cancellation import cancel_token
from ...utils.progress import ProgressReporter
from .formatting import estimate_eta_seconds
from .i18n import get_locale_from_app, step_labels, t
from .key_bindings import layout_binding
from .pipeline_runner import PipelineRunner
from .steps import StepBack, StepCancel, StepComplete
from .steps.advanced import AdvancedStep
from .steps.mods import ModsStep
from .steps.paths import PathsStep
from .steps.provider import ProviderStep
from .steps.summary import SummaryStep
from .steps.translate_run import TranslateRunStep
from .steps.welcome import WelcomeStep

# ── Shared state ──────────────────────────────────────────────────


def _extract_widget_text(widget: Widget) -> str:
    """Extract human-readable text from a widget for clipboard copy.

    Walks parent chain for widgets that delegate their text to a child
    (e.g. horizontal containers with a Label child).
    """
    from textual.widgets import Button, Input, Label, RichLog, Select, Switch

    if isinstance(widget, Input):
        return str(widget.value or "")
    if isinstance(widget, Label):
        return _strip_markup(str(widget.content))
    if isinstance(widget, Button):
        return str(widget.label)
    if isinstance(widget, Switch):
        return ""
    if isinstance(widget, Select):
        val = widget.value
        if val is None or val == Select.BLANK:
            return ""
        for option in widget._options:
            if option[1] == val:
                return str(option[0])
        return str(val)
    if isinstance(widget, RichLog):
        lines: list[str] = []
        # Textual 8.x stores content in self.lines (list[Strip])
        for strip in widget.lines:
            if hasattr(strip, "text") and strip.text.strip():
                lines.append(strip.text)
        # Fall back to deferred renders if not yet mounted
        if not lines:
            for deferred in widget._deferred_renders:
                content = deferred[0]
                if isinstance(content, str):
                    lines.append(content)
                elif hasattr(content, "plain"):
                    lines.append(content.plain)
        return "\n".join(lines)

    # ── Containers — try first text-bearing child ──────────────
    if isinstance(widget, (Container, Horizontal, Vertical, Widget)):
        parts: list[str] = []
        for child in widget.children:
            text = _extract_widget_text(child)
            if text.strip():
                parts.append(text)
        return "\n".join(parts)

    # ── SelectionList → selected items ─────────────────────────
    try:
        from textual.widgets import SelectionList

        if isinstance(widget, SelectionList):
            items: list[str] = []
            for i in sorted(widget.selected):
                option = widget._options[i]
                label = option[0] if isinstance(option, tuple) else str(option)
                items.append(str(label).strip())
            return "\n".join(items)
    except ImportError:
        pass

    # ── RadioSet / RadioButton ────────────────────────────────
    try:
        from textual.widgets import RadioButton, RadioSet

        if isinstance(widget, RadioButton):
            return str(widget.label if hasattr(widget, "label") else "")
        if isinstance(widget, RadioSet):
            pressed = widget.pressed_button
            if pressed is not None:
                return _extract_widget_text(pressed)
    except ImportError:
        pass

    # ── DataTable → cell under cursor (best-effort) ────────────
    try:
        from textual.widgets import DataTable

        if isinstance(widget, DataTable):
            if widget.cursor_cell != (0, 0):
                row, col = widget.cursor_cell
                cell = widget.get_cell_at((row, col))
                if cell is not None:
                    return str(cell)
            return ""
    except ImportError:
        pass

    return ""


def _strip_markup(text: str) -> str:
    """Remove Textual/Rich markup tags and return plain text."""
    try:
        from rich.text import Text

        return Text.from_markup(text).plain
    except ImportError:
        pass
    # Fallback: basic tag stripping
    import re

    return re.sub(r"\[/?[^\]]*\]", "", text)


@dataclass
class WizardState:
    """Mutable state shared across wizard steps via app.wizard_state."""

    settings: Settings = field(default_factory=Settings)
    config_path: Path | None = None
    mod_infos: list[ModInfo] = field(default_factory=list)
    selected_mod_infos: list[ModInfo] = field(default_factory=list)
    progress_reporter: ProgressReporter | None = None
    pipeline_result: PipelineResult | None = None
    ui_locale: str = "en"


# ── Containers ────────────────────────────────────────────────────


class StepCard(Container):
    """Animated step card — holds the current step widget."""

    DEFAULT_CSS = """
    StepCard {
        width: 100%;
        height: 1fr;
        background: $surface;
        border: round $border;
        padding: 0;
        overflow: auto;
    }
    """


# ── Stepper header ────────────────────────────────────────────────


class Stepper(Widget):
    """Step indicator — dots with connectors + active step name/counter."""

    DEFAULT_CSS = """
    Stepper {
        width: 100%;
        height: 3;
        background: $panel;
        padding: 1 2 0 2;
        layout: vertical;
    }
    Stepper > #stepper-dots { width: 100%; height: 1; align: center middle; layout: horizontal; }
    Stepper > #stepper-dots > Label { width: auto; }
    Stepper > #stepper-dots > .seg-done { color: $success; }
    Stepper > #stepper-dots > .seg-active { color: $accent; text-style: bold; }
    Stepper > #stepper-dots > .seg-upcoming { color: $text-muted; }
    Stepper > #stepper-dots > .seg-conn { color: $text-muted; }
    Stepper > #stepper-label { width: 100%; height: 1; content-align: center middle; color: $text-muted; }
    """

    current: reactive[int] = reactive(-1)
    _dots: list[Label]
    _locale: str = "en"

    def compose(self) -> ComposeResult:
        self._dots = []
        labels = step_labels(self._locale)
        with Horizontal(id="stepper-dots"):
            for i in range(len(labels)):
                dot = Label("○", id=f"seg-{i}", classes="seg-upcoming")
                self._dots.append(dot)
                yield dot
                if i < len(labels) - 1:
                    yield Label("──", classes="seg-conn")
        yield Label("", id="stepper-label")

    def set_locale(self, locale: str) -> None:
        self._locale = locale
        self.watch_current(self.current)

    def watch_current(self, value: int) -> None:
        for i, dot in enumerate(self._dots):
            dot.remove_class("seg-done", "seg-active", "seg-upcoming")
            if i < value:
                dot.update("●")
                dot.add_class("seg-done")
            elif i == value:
                dot.update("●")
                dot.add_class("seg-active")
            else:
                dot.update("○")
                dot.add_class("seg-upcoming")
        try:
            label = self.query_one("#stepper-label", Label)
        except Exception:
            return
        labels = step_labels(self._locale)
        total = len(labels)
        if 0 <= value < total:
            label.update(
                t(
                    "stepper.progress",
                    self._locale,
                    name=labels[value],
                    current=value + 1,
                    total=total,
                )
            )
        elif value >= total:
            label.update(t("stepper.done", self._locale))

    def mark_all_done(self) -> None:
        self.current = len(step_labels(self._locale))


# ── WizardScreen (main controller) ────────────────────────────────


class WizardScreen(Screen):
    """Wizard screen — stepper header + step card + footer keybar.

    Manages step transitions. All step widgets are pre-created and
    mounted in ``compose()``; navigating only toggles ``display``,
    with zero DOM creation after startup.

    On restart (New Translation) the cache is cleared so fresh step
    widgets are created on the next ``compose()`` cycle.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("enter", "advance_from_key", "Next", show=True),
        Binding("tab", "focus_next", "Focus", show=True),
        *layout_binding("q", "quit_cancel", "Quit", show=False),
        *layout_binding("ctrl+c", "quit_cancel", "Quit", show=False),
        *layout_binding("ctrl+q", "quit_cancel", "Quit", show=False),
        *layout_binding("ctrl+l", "toggle_log", "Log", show=False),
        Binding("ctrl+shift+l", "toggle_qa_log", "QA Log", show=False),
    ]

    # Step registry — index 0 through 5
    STEPS: ClassVar[list[type[Widget]]] = [
        WelcomeStep,
        ProviderStep,
        PathsStep,
        AdvancedStep,
        ModsStep,
        TranslateRunStep,
    ]

    current_index: int = -1
    _current_step: Widget | None = None
    _step_cache: dict[int, Widget]
    _card: StepCard | None = None
    _stepper: Stepper | None = None
    _pipeline_running: bool = False
    _runner: PipelineRunner | None = None

    # ── Pipeline messages ─────────────────────────────────────────

    class PipelineDone(Message):
        def __init__(self, stats: OverallStats) -> None:
            self.stats = stats
            super().__init__()

    class PipelineError(Message):
        def __init__(self, error: str) -> None:
            self.error = error
            super().__init__()

    class PipelineProgress(Message):
        """Thread-safe progress event (post_message from worker threads)."""

        def __init__(self, event: str, data: dict[str, Any]) -> None:
            self.event = event
            self.data = data
            super().__init__()

    class PipelineLogLine(Message):
        """Thread-safe log line from loguru sink."""

        def __init__(self, line: str) -> None:
            self.line = line
            super().__init__()

    # ── Init ──────────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__()
        self._step_cache = {}

    # ── Compose & mount ───────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Stepper(id="stepper")

        # Load config + .env before creating steps so they get correct
        # initial_* values from the start.
        try:
            from dotenv import load_dotenv as _ld

            _ld()
        except ImportError:
            pass
        try:
            config_path = find_config_file(self.app.wizard_state.settings.mods_path)  # type: ignore[attr-defined]
            if config_path:
                config_data = load_config(config_path)
                wiz = self.app.wizard_state  # type: ignore[attr-defined]
                wiz.settings = Settings(config_data=config_data)
                wiz.config_path = config_path
                if config_data.get("ui_locale") in ("en", "uk"):
                    wiz.ui_locale = str(config_data["ui_locale"])
                logger.info("Loaded config from {}", config_path)
        except Exception:
            logger.exception("Failed to load config")
        # Pre-create and mount ALL steps upfront so navigation is
        # instant — just toggles display (zero mount calls at runtime).
        with StepCard(id="step-card"):
            for idx, step_cls in enumerate(self.STEPS):
                step = step_cls()
                self._step_cache[idx] = step
                # Inject initial values before mount so compose()
                # sees them from the start.  On restart the cache
                # is cleared, so fresh values are injected next time.
                self._inject_initial_values(step, idx)
                if idx == 0:
                    yield step
                else:
                    step.display = False
                    yield step
        yield Footer()

    def on_mount(self) -> None:
        """Mark welcome step as active."""
        # WelcomeStep already mounted in compose — just update state
        self._current_step = self.query_one(WelcomeStep)
        self.current_index = 0
        self._stepper = self.query_one("#stepper", Stepper)
        wiz = self.app.wizard_state  # type: ignore[attr-defined]
        self._stepper.set_locale(wiz.ui_locale)
        self._stepper.current = 0
        self._card = self.query_one("#step-card", StepCard)
        self._apply_locale_to_step(self._current_step)

    # ── Step transitions ──────────────────────────────────────────

    def _show_step(self, index: int) -> None:
        """Transition to *index* — instant (all steps pre-mounted)."""
        self._swap_step(index)

    def _swap_step(self, index: int) -> None:
        """Show the step at *index* — just toggles display."""
        # Hide the currently visible step
        if self._current_step is not None and self._current_step.is_attached:
            self._current_step.display = False

        self.current_index = index

        if 0 <= index < len(self.STEPS):
            if index in self._step_cache:
                step = self._step_cache[index]
            else:
                # Re-create the step widget (cache was cleared, e.g. on restart)
                step_cls = self.STEPS[index]
                step = step_cls()
                self._step_cache[index] = step
                self._inject_initial_values(step, index)
                card = self._card or self.query_one("#step-card", StepCard)
                step.display = False  # hidden until we toggle it below
                card.mount(step)
            step.display = True
            self._current_step = step

        self._stepper.current = index  # type: ignore[union-attr]

        self._apply_locale_to_step(self._current_step)

        if index == 2:
            self._refresh_paths_step()
        elif index == 3:
            self._refresh_advanced_step()
        elif index == 4:
            self._refresh_mods_step()
        elif index == 5:
            with contextlib.suppress(Exception):
                self.query_one(TranslateRunStep).clear_error()

    def _apply_locale_to_step(self, step: Widget | None) -> None:
        if step is not None and hasattr(step, "apply_locale"):
            with contextlib.suppress(Exception):
                step.apply_locale()  # type: ignore[attr-defined]

    def on_locale_changed(self) -> None:
        """Propagate locale change to stepper and all cached steps."""
        locale = get_locale_from_app(self.app)
        if self._stepper is not None:
            self._stepper.set_locale(locale)
        for step in self._step_cache.values():
            self._apply_locale_to_step(step)
        self.refresh_bindings()

    def _refresh_paths_step(self) -> None:
        try:
            step = self._step_cache.get(2)
            if step is not None and hasattr(step, "refresh_on_show"):
                step.refresh_on_show()  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to refresh paths step")

    def _refresh_advanced_step(self) -> None:
        """Refresh AdvancedStep dynamic content (QA model label, chunk visibility)."""
        try:
            step = self._step_cache.get(3)
            if step is not None and hasattr(step, "refresh_on_show"):
                step.refresh_on_show()  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to refresh advanced step")

    def _refresh_mods_step(self) -> None:
        """Re-populate the mods list from current wizard state."""
        try:
            step = self._step_cache[4]
            if hasattr(step, "refresh_mods"):
                step.refresh_mods()  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to refresh mods step")

    def _inject_initial_values(self, step: Widget, index: int) -> None:
        """Inject saved settings as defaults before compose/mount."""
        wiz = self.app.wizard_state  # type: ignore[attr-defined]
        if index == 1:
            if hasattr(step, "initial_provider"):
                step.initial_provider = wiz.settings.provider  # type: ignore[attr-defined]
            if hasattr(step, "initial_model"):
                step.initial_model = wiz.settings.model or ""  # type: ignore[attr-defined]
        elif index == 2:
            if hasattr(step, "initial_source"):
                step.initial_source = wiz.settings.source_mc_lang  # type: ignore[attr-defined]
            if hasattr(step, "initial_target"):
                step.initial_target = wiz.settings.target_mc_lang  # type: ignore[attr-defined]
            if hasattr(step, "initial_mods_path"):
                step.initial_mods_path = wiz.settings.mods_path  # type: ignore[attr-defined]
            if hasattr(step, "initial_output_path"):
                step.initial_output_path = wiz.settings.translation_path  # type: ignore[attr-defined]
        elif index == 3:
            if hasattr(step, "initial_no_cache"):
                step.initial_no_cache = wiz.settings.no_cache  # type: ignore[attr-defined]
            if hasattr(step, "initial_workers"):
                step.initial_workers = wiz.settings.max_workers  # type: ignore[attr-defined]
            if hasattr(step, "initial_hint_lang"):
                step.initial_hint_lang = wiz.settings.hint_lang  # type: ignore[attr-defined]
            if hasattr(step, "initial_glossary_path"):
                step.initial_glossary_path = wiz.settings.glossary_path or ""  # type: ignore[attr-defined]
            if hasattr(step, "initial_output_mode"):
                step.initial_output_mode = wiz.settings.output_mode  # type: ignore[attr-defined]
            if hasattr(step, "initial_qa_judge"):
                step.initial_qa_judge = wiz.settings.qa_judge  # type: ignore[attr-defined]
            if hasattr(step, "initial_qa_judge_model"):
                step.initial_qa_judge_model = wiz.settings.qa_judge_model or ""  # type: ignore[attr-defined]
            if hasattr(step, "initial_qa_judge_provider"):
                step.initial_qa_judge_provider = wiz.settings.qa_judge_provider or ""  # type: ignore[attr-defined]
            if hasattr(step, "initial_qa_threshold"):
                step.initial_qa_threshold = wiz.settings.qa_threshold  # type: ignore[attr-defined]
            if hasattr(step, "initial_qa_max_attempts"):
                step.initial_qa_max_attempts = wiz.settings.qa_max_attempts  # type: ignore[attr-defined]
            if hasattr(step, "initial_dry_run"):
                step.initial_dry_run = wiz.settings.dry_run  # type: ignore[attr-defined]
            if hasattr(step, "initial_qa_chunk_size"):
                step.initial_qa_chunk_size = wiz.settings.qa_chunk_size  # type: ignore[attr-defined]
            if hasattr(step, "initial_qa_judge_workers"):
                step.initial_qa_judge_workers = wiz.settings.qa_judge_workers  # type: ignore[attr-defined]
            if hasattr(step, "initial_chunk_mode"):
                step.initial_chunk_mode = wiz.settings.chunk_mode  # type: ignore[attr-defined]
            if hasattr(step, "initial_chunk_size"):
                step.initial_chunk_size = wiz.settings.chunk_size  # type: ignore[attr-defined]
            if hasattr(step, "initial_chunk_token_budget"):
                step.initial_chunk_token_budget = wiz.settings.chunk_token_budget  # type: ignore[attr-defined]
            if hasattr(step, "initial_progress_batch_size"):
                step.initial_progress_batch_size = wiz.settings.progress_batch_size  # type: ignore[attr-defined]
            if hasattr(step, "initial_rate_limit_rpm"):
                step.initial_rate_limit_rpm = wiz.settings.rate_limit_rpm  # type: ignore[attr-defined]
            if hasattr(step, "initial_rate_limit_burst"):
                step.initial_rate_limit_burst = wiz.settings.rate_limit_burst  # type: ignore[attr-defined]
            judge_limits = wiz.settings.rate_limit_services.get("judge", {})
            if hasattr(step, "initial_judge_rpm"):
                step.initial_judge_rpm = judge_limits.get("rpm")  # type: ignore[attr-defined]
            if hasattr(step, "initial_judge_burst"):
                step.initial_judge_burst = judge_limits.get("burst")  # type: ignore[attr-defined]

    # ── Navigation ────────────────────────────────────────────────

    def advance(self, data: dict | None = None) -> None:
        """Advance to next step."""
        idx = self.current_index

        if idx == 1 and data:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            wiz.settings.provider = data.get("provider", "google")
            if "model" in data:
                wiz.settings.model = data["model"]

        elif idx == 2 and data:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            wiz.settings.source_mc_lang = data.get("source_lang", "en_US")
            wiz.settings.target_mc_lang = data.get("target_lang", "es_ES")
            wiz.settings.mods_path = data.get("mods_path", "./mods")
            wiz.settings.translation_path = data.get("output_path", "./translated_mods")
            try:
                scanner = ModScanner(wiz.settings.mods_path, source_lang=wiz.settings.source_mc_lang)
                wiz.mod_infos = scanner.discover_mods()
            except Exception:
                logger.exception("Mod scanning failed")
                wiz.mod_infos = []

        elif idx == 3 and data:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            wiz.settings.no_cache = data.get("no_cache", False)
            wiz.settings.dry_run = data.get("dry_run", False)
            wiz.settings.max_workers = data.get("workers", 4)
            wiz.settings.hint_lang = data.get("hint_lang")
            wiz.settings.glossary_path = data.get("glossary_path")
            if "output_mode" in data:
                wiz.settings.output_mode = data["output_mode"]
            if "qa_judge" in data:
                wiz.settings.qa_judge = bool(data["qa_judge"])
            if "qa_judge_provider" in data:
                wiz.settings.qa_judge_provider = data["qa_judge_provider"]
            if "qa_judge_model" in data:
                wiz.settings.qa_judge_model = data["qa_judge_model"]
            if "qa_threshold" in data:
                wiz.settings.qa_threshold = int(data["qa_threshold"])
            if "qa_max_attempts" in data:
                wiz.settings.qa_max_attempts = int(data["qa_max_attempts"])
            if "chunk_mode" in data:
                wiz.settings.chunk_mode = str(data["chunk_mode"])
            if "chunk_size" in data:
                wiz.settings.chunk_size = data["chunk_size"]
            if "chunk_token_budget" in data:
                wiz.settings.chunk_token_budget = int(data["chunk_token_budget"])
            if "progress_batch_size" in data:
                wiz.settings.progress_batch_size = int(data["progress_batch_size"])
            if "qa_chunk_size" in data:
                wiz.settings.qa_chunk_size = int(data["qa_chunk_size"])
            if "qa_judge_workers" in data:
                wiz.settings.qa_judge_workers = int(data["qa_judge_workers"])
            rate_limit = data.get("rate_limit")
            if isinstance(rate_limit, dict):
                wiz.settings.rate_limit_rpm = rate_limit.get("rpm")
                wiz.settings.rate_limit_burst = rate_limit.get("burst")
                judge_cfg = rate_limit.get("judge")
                if isinstance(judge_cfg, dict):
                    wiz.settings.rate_limit_services["judge"] = {
                        k: float(v) for k, v in judge_cfg.items() if k in ("rpm", "burst")
                    }
                elif "judge" not in rate_limit:
                    wiz.settings.rate_limit_services.pop("judge", None)

        if idx == 4:
            self._start_pipeline()
        elif idx == 5:
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            if wiz.pipeline_result:
                self.show_summary(wiz.pipeline_result.stats)
        else:
            nxt = idx + 1
            if nxt < len(self.STEPS):
                self._show_step(nxt)

    def go_back(self) -> None:
        """Go to previous step (or back to mods from summary)."""
        from loguru import logger

        logger.debug(
            "WizardScreen.go_back() called, current_index={}, STEPS_len={}",
            self.current_index,
            len(self.STEPS),
        )
        if self._pipeline_running and self.current_index == 5:
            locale = get_locale_from_app(self.app)
            self.app.notify(t("notify.pipeline_running", locale), timeout=4)
            return
        if self.current_index <= 0:
            return
        if self.current_index >= len(self.STEPS):  # on summary
            self._show_step(4)  # back to Mods
        else:
            self._show_step(self.current_index - 1)

    def show_summary(self, stats: OverallStats) -> None:
        """Display summary with stats after pipeline completes.

        SummaryStep is also pre-created and cached when first shown.
        """
        summary_key = len(self.STEPS)  # 6

        # Hide current step
        if self._current_step is not None and self._current_step.is_attached:
            self._current_step.display = False

        if summary_key in self._step_cache:
            step = self._step_cache[summary_key]
        else:
            step = SummaryStep()
            self._step_cache[summary_key] = step
            self._card.mount(step)  # type: ignore[union-attr]

        step.set_stats(stats)  # type: ignore[attr-defined]
        step.display = True
        self._apply_locale_to_step(step)

        self._current_step = step
        self.current_index = len(self.STEPS)
        self._stepper.mark_all_done()  # type: ignore[union-attr]

        locale = get_locale_from_app(self.app)
        self.app.notify(t("notify.translation_complete", locale), timeout=2)
        self.set_focus(step)

    # ── Pipeline worker ───────────────────────────────────────────

    def _start_pipeline(self) -> None:
        """Start translation pipeline via PipelineRunner."""
        cancel_token.clear()
        self._show_step(5)
        wiz = self.app.wizard_state  # type: ignore[attr-defined]
        if wiz.settings.output_mode == "replace":
            wiz.settings.translation_path = wiz.settings.mods_path

        # Show/hide QA panel and progress bar
        try:
            step = self.query_one(TranslateRunStep)
            qa_visible = wiz.settings.qa_judge
            step.query_one("#qa-panel").display = qa_visible
            step.query_one("#qa-progress-block").display = "block" if qa_visible else "none"
        except Exception:
            pass

        selected = wiz.selected_mod_infos
        if not selected:
            locale = get_locale_from_app(self.app)
            with contextlib.suppress(Exception):
                tr = self.query_one(TranslateRunStep)
                tr.add_log(t("translate.no_mods", locale))
                tr.show_error(t("mods.error_none_selected", locale))
            return

        self._pipeline_running = True
        self._pipeline_start = time.monotonic()

        # ── Callbacks bridge runner → UI (thread-safe via post_message) ──
        def _on_progress(event: str, data: dict[str, Any]) -> None:
            if threading.get_ident() == self.app._thread_id:
                self._apply_progress_event(event, **data)
            else:
                self.post_message(self.PipelineProgress(event, data))

        def _on_log(line: str) -> None:
            if threading.get_ident() == self.app._thread_id:
                self._append_pipeline_log(line)
            else:
                self.post_message(self.PipelineLogLine(line))

        def _on_done(stats: OverallStats) -> None:
            from ...application.pipeline import PipelineResult

            wiz.pipeline_result = PipelineResult(stats=stats, mods=[], workspace_path=Path())
            self.post_message(self.PipelineDone(stats))

        def _on_error(error: str) -> None:
            self.post_message(self.PipelineError(error))

        self._runner = PipelineRunner(
            wiz.settings,
            selected,
            on_progress=_on_progress,
            on_log=_on_log,
            on_done=_on_done,
            on_error=_on_error,
            is_debug=getattr(self.app, "_debug", False),
        )
        self._runner.start()
        wiz.progress_reporter = self._runner.reporter

        self.run_worker(
            self._runner.run,  # type: ignore[arg-type]
            name="pipeline",
            group="default",
            thread=False,
            exit_on_error=False,
        )

    def _apply_progress_event(self, event: str, **kw: Any) -> None:
        """Apply a progress event to TranslateRunStep (main thread only)."""
        try:
            step = self.query_one(TranslateRunStep)
        except Exception:
            return

        if event == "title":
            step.set_phase(kw.get("text", ""))
        elif event == "mod_start":
            step.set_mod_name(kw.get("mod_name", ""))
        elif event == "mod_file_start":
            step.set_current_file(kw.get("file_path", ""))
        elif event == "entry_progress":
            step.update_entries(kw.get("done", 0), kw.get("total", 0))
        elif event == "overall_progress":
            done = kw.get("completed_entries", 0)
            total = kw.get("total_entries", 0)
            step.update_mods(
                kw.get("completed_mods", 0),
                kw.get("total_mods", 0),
                fractional=kw.get("fractional_mods"),
            )
            step.update_entries(done, total)
            elapsed = time.monotonic() - getattr(self, "_pipeline_start", time.monotonic())
            eta = estimate_eta_seconds(done, total, elapsed)
            step.update_live_stats(elapsed, eta, kw.get("failed_entries", 0))
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            if wiz.settings.qa_judge:
                qa_bar = step.query_one("#qa-progress", ProgressBar)
                qa_done = int(qa_bar.progress)
                step.update_qa(qa_done, total)
        elif event == "qa_progress":
            step.update_qa(kw.get("done", 0), kw.get("total", 0))
        elif event == "mod_file_complete":
            name = Path(kw.get("file_path", "")).name
            errors = kw.get("errors", 0)
            duration_ms = kw.get("duration_ms", 0)
            err_part = f", {errors} failed" if errors else ""
            step.add_log(f"[dim]  {name}: done in {duration_ms / 1000:.1f}s{err_part}[/]")
        elif event == "mod_complete":
            mod_name = kw.get("mod_name", "")
            translated = kw.get("translated", 0)
            total = kw.get("total", 0)
            failed = kw.get("failed", 0)
            if total > 0:
                fail_part = f", {failed} failed" if failed else ""
                step.add_log(f"[bold green]✓ {mod_name} done ({translated}/{total}{fail_part})[/]")
            else:
                step.add_log(f"[bold green]✓ {mod_name} done[/]")
        elif event == "translated_entry":
            s = kw.get("source", "")
            t = kw.get("translated", "")
            # Replace newlines with visible \n so log stays single-line
            s_disp = s.replace("\n", "\\n")
            t_disp = t.replace("\n", "\\n")
            step.add_log(f"  [bold white]{s_disp}[/] → [bold green]{t_disp}[/]")

        # ── QA events ───────────────────────────────────────────────
        elif event == "qa_start":
            from ...domain.qa_display import format_provider_model

            label = format_provider_model(kw.get("provider", ""), kw.get("model", ""))
            step.add_qa_log(f"[bold cyan]───── ◆ Reviewing {kw['total']} entries via {label} ─────[/]")
        elif event == "qa_verdict":
            icon = "⚠" if kw.get("is_flagged") else "✓"
            score = kw.get("score", 0)
            key = kw.get("key", "?")
            issue = kw.get("issue")
            line = f"  {icon} [bold]{key}[/]: scored [bold]{score}/5[/]"
            if issue:
                line += f" — {issue}"
            step.add_qa_log(line)
        elif event == "qa_correction":
            from ...domain.qa_display import format_qa_correction_line

            line = format_qa_correction_line(
                key=kw.get("key", "?"),
                accepted=kw.get("accepted", False),
                attempt=kw.get("attempt", 0),
                max_attempts=kw.get("max_attempts", 1),
            )
            step.add_qa_log(f"[bold]{line}[/]")
        elif event == "qa_warning":
            key = kw.get("key", "?")
            msg = kw.get("message", "")
            step.add_qa_log(f"  [yellow]⚡ {key}: {msg}[/]")
        elif event == "qa_done":
            flagged = kw.get("flagged", 0)
            corrected = kw.get("corrected", 0)
            step.add_qa_log(f"[bold green]───── ✓ QA complete: {flagged} flagged, {corrected} corrected ─────[/]")
        elif event == "qa_inline_status":
            message = kw.get("message")
            if message:
                step.add_qa_log(f"[dim cyan]{message}[/]")
            else:
                from ...domain.qa_display import format_provider_model

                provider = kw.get("provider", "")
                model = kw.get("model", "")
                label = format_provider_model(provider, model)
                step.add_qa_log(f"[bold cyan]───── Inline QA active ({label}) ─────[/]")
        elif event == "qa_inline_judging":
            count = kw.get("count", 0)
            chunk_size = kw.get("chunk_size", 0)
            step.add_qa_log(f"[dim cyan]→ judging {count} item(s) (chunk={chunk_size})[/]")
        elif event == "qa_inline_fix":
            key = kw.get("key", "?")
            orig = kw.get("original", "")
            fixed = kw.get("fixed", "")
            orig_disp = orig.replace("\n", "\\n")
            fixed_disp = fixed.replace("\n", "\\n")
            step.add_qa_log(f"  [green]✓[/] [bold]{key}[/]: [white]{orig_disp}[/] → [bold green]{fixed_disp}[/]")
        elif event == "qa_inline_summary":
            flagged = kw.get("flagged", 0)
            total = kw.get("total", 0)
            corrected = kw.get("corrected", 0)
            elapsed = kw.get("elapsed", 0.0)
            step.add_qa_log(
                f"[bold yellow]← {flagged}/{total} flagged, {corrected}/{flagged} corrected[/] [dim]({elapsed:.1f}s)[/]"
            )
        elif event == "qa_inline_error":
            message = kw.get("message", "")
            elapsed = kw.get("elapsed", 0.0)
            step.add_qa_log(f"[bold red]✗ judge failed[/] [dim]({elapsed:.1f}s): {message}[/]")

    # ── Message handlers ──────────────────────────────────────────

    def _clear_cache(self) -> None:
        """Remove all cached step widgets so they get fresh initial values."""
        for step in self._step_cache.values():
            if step.is_attached:
                with contextlib.suppress(Exception):
                    step.remove()
        self._step_cache.clear()
        self._current_step = None

    def on_step_complete(self, message: StepComplete) -> None:
        if message.data and message.data.get("restart"):
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            wiz.pipeline_result = None
            wiz.selected_mod_infos = []
            wiz.mod_infos = []
            self._clear_cache()
            self._show_step(0)
        else:
            self.advance(message.data)

    def on_step_back(self, _message: StepBack) -> None:
        self.go_back()

    def on_step_cancel(self, _message: StepCancel) -> None:
        from ...utils.shutdown import request_shutdown

        request_shutdown(0)

    def _close_log_sink(self) -> None:
        """Remove the loguru → TUI sink (delegates to runner)."""
        if hasattr(self, "_runner") and self._runner is not None:
            self._runner.stop()

    def _append_pipeline_log(self, line: str) -> None:
        with contextlib.suppress(Exception):
            self.query_one(TranslateRunStep).add_log(line)

    def on_wizard_screen_pipeline_progress(self, message: PipelineProgress) -> None:
        self._apply_progress_event(message.event, **message.data)

    def on_wizard_screen_pipeline_log_line(self, message: PipelineLogLine) -> None:
        self._append_pipeline_log(message.line)

    def on_wizard_screen_pipeline_done(self, message: PipelineDone) -> None:
        self._pipeline_running = False
        self._close_log_sink()
        self.show_summary(message.stats)

    def on_wizard_screen_pipeline_error(self, message: PipelineError) -> None:
        self._pipeline_running = False
        self._close_log_sink()
        with contextlib.suppress(Exception):
            tr = self.query_one(TranslateRunStep)
            tr.add_log(f"[red]{message.error}[/]")
            tr.show_error(message.error)

    # ── Actions ───────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.go_back()

    def action_advance_from_key(self) -> None:
        """Enter key → trigger Start/Next/Continue/Translate button."""
        if self._current_step is None:
            return
        for btn_id in ("start-btn", "next-btn"):
            with contextlib.suppress(Exception):
                btn = self._current_step.query_one(f"#{btn_id}", Button)
                if btn:
                    btn.press()
                    return

    def action_focus_next(self) -> None:
        """Tab → advance focus."""
        self.screen.focus_next()

    def action_quit_cancel(self) -> None:
        from ...utils.shutdown import request_shutdown

        request_shutdown(0)

    def key_ctrl_c(self) -> None:
        """Fallback Ctrl+C handler on the wizard screen."""
        from ...utils.shutdown import request_shutdown

        request_shutdown(0)

    def on_unmount(self) -> None:
        """Cancel pipeline workers and detach log sink when wizard closes."""
        cancel_token.set()
        self._close_log_sink()
        if hasattr(self, "_runner") and self._runner is not None:
            self._runner.stop()
        with contextlib.suppress(Exception):
            self.app.workers.cancel_group("default")  # type: ignore[call-arg, arg-type]

    def action_toggle_log(self) -> None:
        """Toggle log panel (only works on translate step)."""
        if self.current_index == 5:
            with contextlib.suppress(Exception):
                self.query_one(TranslateRunStep).toggle_log()

    def action_toggle_qa_log(self) -> None:
        """Toggle QA log panel (only works on translate step)."""
        if self.current_index == 5:
            with contextlib.suppress(Exception):
                self.query_one(TranslateRunStep).toggle_qa_log()

    # ── Right-click & clipboard ────────────────────────────────────

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy *text* to system clipboard and notify user."""
        if not text.strip():
            return
        ok = False
        tmp = ""
        if sys.platform == "win32":
            try:
                # Use PowerShell Set-Clipboard (Unicode-safe)
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
                    f.write(text)
                    tmp = f.name
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f"Get-Content -Encoding UTF8 '{tmp}' | Set-Clipboard",
                    ],
                    check=True,
                    timeout=10,
                )
                ok = True
            except (subprocess.SubprocessError, OSError):
                pass
            finally:
                if tmp:
                    with contextlib.suppress(Exception):
                        Path(tmp).unlink(missing_ok=True)
        if not ok:
            try:
                import pyperclip  # type: ignore[import-untyped]

                pyperclip.copy(text)
                ok = True
            except (ImportError, Exception):
                pass
        if not ok:
            try:
                import base64

                encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
                print(f"\x1b]52;c;{encoded}\a", end="", flush=True)
                ok = True
            except Exception:
                pass
        if ok:
            lines = text.count("\n") + 1
            locale = get_locale_from_app(self.app)
            self.app.notify(t("notify.copied", locale, lines=lines), timeout=2)
        else:
            locale = get_locale_from_app(self.app)
            self.app.notify(t("notify.copy_failed", locale), timeout=3)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Right-click → copy the widget under cursor to clipboard."""
        if event.button != 3:
            return
        event.stop()

        if self._current_step is None:
            locale = get_locale_from_app(self.app)
            self.app.notify(t("notify.no_copy", locale), timeout=2)
            return

        step = self._current_step
        step_region = step.region

        # Only process clicks within the current step's visible region
        if step_region.contains(event.screen_x, event.screen_y):
            # Convert to step-relative coordinates and find the child widget
            local_x = event.screen_x - step_region.x
            local_y = event.screen_y - step_region.y
            try:
                widget, _region = step.get_widget_at(local_x, local_y)  # type: ignore[attr-defined]
            except Exception:
                widget = step

            text = _extract_widget_text(widget)
            if text.strip():
                self._copy_to_clipboard(text)
                return

        self.app.notify("⚠ No text to copy here", timeout=2)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Prevent terminal paste on right-click release."""
        if event.button == 3:
            event.stop()
