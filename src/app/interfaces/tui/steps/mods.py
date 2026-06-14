"""Step 4: Mod selection — SelectionList of discovered JAR mods."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import Button, Label, SelectionList

from ..i18n import get_locale_from_app, t
from . import StepBack, StepComplete


class ModsStep(Widget):
    """View and select mods from the discovered list."""

    DEFAULT_CSS = """
    ModsStep {
        layout: vertical;
        width: 100%;
        height: 100%;
    }
    ModsStep > #mods-toolbar {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: left middle;
        margin: 0 0 1 0;
    }
    ModsStep > #mods-toolbar > #mods-status {
        width: 1fr;
        color: $text-muted;
    }
    ModsStep > #mods-toolbar > .mods-actions {
        width: auto;
        height: auto;
        align: right middle;
    }
    ModsStep > #mods-toolbar > .mods-actions > Button {
        width: 16;
        margin: 0 0 0 1;
    }
    ModsStep > #mods-error {
        color: $error;
        text-style: bold;
        margin: 0 0 1 0;
    }
    ModsStep > #mods-list-wrap {
        width: 100%;
        height: 1fr;
        min-height: 8;
        margin: 0 0 1 0;
    }
    ModsStep > #mods-list-wrap > SelectionList {
        width: 100%;
        height: 100%;
    }
    ModsStep > #nav-row {
        width: 100%;
        height: auto;
        margin: 2 0 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        locale = get_locale_from_app(self.app)
        yield Label(t("mods.title", locale), classes="step-title")
        with Horizontal(id="mods-toolbar"):
            yield Label(t("mods.scanning", locale), id="mods-status")
            with Horizontal(classes="mods-actions"):
                yield Button(t("mods.select_all", locale), id="select-all-btn")
                yield Button(t("mods.deselect_all", locale), id="deselect-all-btn")
        yield Label("", id="mods-error")
        with Container(id="mods-list-wrap"):
            yield SelectionList[int](id="mods-list")
        yield Horizontal(
            Button(t("nav.back", locale), id="back-btn"),
            Button(t("mods.translate", locale), id="next-btn", variant="primary"),
            id="nav-row",
        )

    def apply_locale(self) -> None:
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        self.query_one(".step-title", Label).update(t("mods.title", locale))
        self.query_one("#select-all-btn", Button).label = t("mods.select_all", locale)
        self.query_one("#deselect-all-btn", Button).label = t("mods.deselect_all", locale)
        self.query_one("#back-btn", Button).label = t("nav.back", locale)
        self.query_one("#next-btn", Button).label = t("mods.translate", locale)
        self.refresh_mods()

    def on_mount(self) -> None:
        self.call_after_refresh(self._init_mods_status)

    def _init_mods_status(self) -> None:
        if not self.is_mounted:
            return
        locale = get_locale_from_app(self.app)
        status = self.query_one("#mods-status", Label)
        wiz = self.app.wizard_state  # type: ignore[attr-defined]
        if not wiz.mod_infos:
            status.update(t("mods.not_found", locale))

    def _mod_label(self, mod: object) -> str:
        locale = get_locale_from_app(self.app)
        name = mod.name  # type: ignore[attr-defined]
        if not mod.has_lang_files:  # type: ignore[attr-defined]
            return t("mods.no_lang", locale, name=name)
        return t(
            "mods.entry_fmt",
            locale,
            name=name,
            entries=mod.estimated_entries,  # type: ignore[attr-defined]
        )

    def refresh_mods(self) -> None:
        wiz = self.app.wizard_state  # type: ignore[attr-defined]
        locale = get_locale_from_app(self.app)
        status = self.query_one("#mods-status", Label)
        slist = self.query_one("#mods-list", SelectionList)
        self.query_one("#mods-error", Label).update("")

        if not wiz.mod_infos:
            status.update(t("mods.not_found", locale))
            slist.clear_options()
            return

        slist.clear_options()
        for i, mod in enumerate(wiz.mod_infos):
            selected = mod.selected if mod.has_lang_files else False
            slist.add_option((self._mod_label(mod), i, selected))
        status.update(t("mods.found", locale, count=len(wiz.mod_infos)))

    def _toggle_all(self, select: bool) -> None:
        slist = self.query_one("#mods-list", SelectionList)
        for i in range(len(slist.options)):
            currently_selected = i in slist.selected
            if (select and not currently_selected) or (not select and currently_selected):
                slist.toggle(i)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        locale = get_locale_from_app(self.app)
        if event.button.id == "select-all-btn":
            self._toggle_all(select=True)
        elif event.button.id == "deselect-all-btn":
            self._toggle_all(select=False)
        elif event.button.id == "next-btn":
            wiz = self.app.wizard_state  # type: ignore[attr-defined]
            error = self.query_one("#mods-error", Label)

            if not wiz.mod_infos:
                error.update(t("mods.error_none_found", locale))
                return

            slist = self.query_one("#mods-list", SelectionList)
            if not slist.selected:
                error.update(t("mods.error_none_selected", locale))
                return

            error.update("")
            wiz.selected_mod_infos = [wiz.mod_infos[i] for i in slist.selected if i < len(wiz.mod_infos)]
            self.post_message(StepComplete())
        elif event.button.id == "back-btn":
            self.post_message(StepBack())
