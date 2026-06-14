"""Smoke tests for the wizard-based Textual TUI."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.interfaces.tui.app import TranslationApp


async def _wait_for_screen(app: TranslationApp, name: str) -> None:
    """Wait until the current screen matches the expected class name."""
    import asyncio

    for _ in range(20):
        if app.screen.__class__.__name__ == name:
            return
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_app_launches_and_shows_wizard() -> None:
    """App launches and shows the wizard screen."""
    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_screen(app, "WizardScreen")
        assert app.screen is not None
        assert app.screen.__class__.__name__ == "WizardScreen"
        await pilot.pause()


@pytest.mark.asyncio
async def test_welcome_step_shows_get_started() -> None:
    """Welcome step is shown first with a Get Started button."""
    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_screen(app, "WizardScreen")
        # WizardScreen should have a Stepper and StepCard
        wizard = app.screen
        assert wizard.query_one("#stepper")
        assert wizard.query_one("#step-card")
        await pilot.pause()


@pytest.mark.asyncio
async def test_save_config_writes_file(tmp_path: Path) -> None:
    """Save config writes a valid movamc.toml."""
    config_file = tmp_path / "movamc.toml"

    from app.core.config_loader import save_config

    data = {
        "source": "en_US",
        "target": "uk_UA",
        "provider": "google",
        "workers": 4,
        "output_mode": "replace",
    }
    saved = save_config(data, config_file)

    assert saved.exists()
    content = saved.read_text(encoding="utf-8")
    assert "en_US" in content
    assert "uk_UA" in content


@pytest.mark.asyncio
async def test_wizard_state_accessible() -> None:
    """WizardState is created and accessible from the app."""
    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 24)) as pilot:
        assert app.wizard_state is not None
        assert hasattr(app.wizard_state, "settings")
        assert hasattr(app.wizard_state, "mod_infos")
        await pilot.pause()


@pytest.mark.asyncio
async def test_advanced_step_qa_section_visible_when_judge_enabled() -> None:
    """AdvancedStep mounts with QA section visible when QA judge is on."""
    from textual.containers import Container

    from app.interfaces.tui.steps.advanced import AdvancedStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 40)) as pilot:
        step = AdvancedStep()
        step.initial_qa_judge = True
        await app.mount(step)
        await pilot.pause()

        qa_section = step.query_one("#qa-section", Container)
        assert qa_section.display is True
        assert step.query_one("#qa-provider-select")
        assert step.query_one("#qa-threshold-input")


@pytest.mark.asyncio
async def test_advanced_step_qa_section_hidden_when_judge_disabled() -> None:
    """AdvancedStep hides QA section when QA judge is off."""
    from textual.containers import Container

    from app.interfaces.tui.steps.advanced import AdvancedStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 40)) as pilot:
        step = AdvancedStep()
        step.initial_qa_judge = False
        await app.mount(step)
        await pilot.pause()
        import asyncio

        await asyncio.sleep(0.15)

        qa_section = step.query_one("#qa-section", Container)
        assert qa_section.display is False


@pytest.mark.asyncio
async def test_advanced_step_toggle_grid() -> None:
    """AdvancedStep uses a 2x2 toggle grid."""
    from app.interfaces.tui.steps.advanced import AdvancedStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 40)) as pilot:
        step = AdvancedStep()
        await app.mount(step)
        await pilot.pause()

        assert step.query_one("#toggle-row-1")
        assert step.query_one("#toggle-row-2")
        assert step.query_one("#no-cache-switch")
        assert step.query_one("#qa-judge-switch")


@pytest.mark.asyncio
async def test_advanced_step_judge_rate_inside_qa_section() -> None:
    """Judge rate-limit inputs live inside the QA section."""
    from textual.containers import Container

    from app.interfaces.tui.steps.advanced import AdvancedStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(100, 50)) as pilot:
        step = AdvancedStep()
        step.initial_qa_judge = True
        await app.mount(step)
        await pilot.pause()

        qa_section = step.query_one("#qa-section", Container)
        assert qa_section.query_one("#judge-rpm-input")
        assert qa_section.query_one("#judge-burst-input")


@pytest.mark.asyncio
async def test_advanced_step_perf_collapsible_collapsed() -> None:
    """Performance tuning section is collapsed by default."""
    from textual.widgets import Collapsible

    from app.interfaces.tui.steps.advanced import AdvancedStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(100, 50)) as pilot:
        step = AdvancedStep()
        await app.mount(step)
        await pilot.pause()

        collapsible = step.query_one("#perf-collapsible", Collapsible)
        assert collapsible.collapsed is True
        assert step.query_one("#chunk-mode-select")
        assert step.query_one("#rate-limit-rpm-input")


@pytest.mark.asyncio
async def test_advanced_refresh_on_show_updates_same_as_translator() -> None:
    """refresh_on_show updates the same-as-translator QA model label."""
    from app.interfaces.tui.steps.advanced import AdvancedStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(100, 50)) as pilot:
        app.wizard_state.settings.provider = "openai"
        app.wizard_state.settings.model = "gpt-4o-mini"

        step = AdvancedStep()
        step.initial_qa_judge = True
        step.initial_qa_judge_provider = ""
        await app.mount(step)
        await pilot.pause()

        step.refresh_on_show()
        await pilot.pause()

        info = step.query_one("#qa-same-info")
        assert "openai" in str(info.content)
        assert "gpt-4o-mini" in str(info.content)


@pytest.mark.asyncio
async def test_advanced_step_performance_fields_present() -> None:
    """AdvancedStep exposes performance and rate-limit controls."""
    from app.interfaces.tui.steps.advanced import AdvancedStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(100, 50)) as pilot:
        step = AdvancedStep()
        step.initial_chunk_mode = "auto"
        step.initial_qa_judge = True
        await app.mount(step)
        await pilot.pause()

        assert step.query_one("#chunk-mode-select")
        assert step.query_one("#progress-batch-input")
        assert step.query_one("#rate-limit-rpm-input")
        assert step.query_one("#judge-rpm-input")
        assert step.query_one("#qa-chunk-size-input")
        assert step.query_one("#qa-judge-workers-input")


@pytest.mark.asyncio
async def test_save_config_writes_performance_sections(tmp_path: Path) -> None:
    """Save config persists chunking, QA performance, and rate_limit sections."""
    config_file = tmp_path / "movamc.toml"

    from app.core.config_loader import save_config

    data = {
        "source": "en_US",
        "target": "uk_UA",
        "provider": "openai",
        "workers": 4,
        "chunk_mode": "auto",
        "progress_batch_size": 10,
        "qa_judge": True,
        "qa_chunk_size": 25,
        "qa_judge_workers": 2,
        "rate_limit": {"rpm": 300, "burst": 20, "judge": {"rpm": 120, "burst": 5}},
    }
    save_config(data, config_file)
    content = config_file.read_text(encoding="utf-8")
    assert "chunk_mode" in content
    assert "[rate_limit]" in content
    assert "judge_workers" in content or "chunk_size" in content


@pytest.mark.asyncio
async def test_cyrillic_ctrl_c_triggers_quit_cancel() -> None:
    """Ctrl+с (Ukrainian layout C key) triggers quit_cancel on the wizard."""
    from app.utils.cancellation import cancel_token

    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_screen(app, "WizardScreen")
        cancel_token.clear()
        await pilot.press("ctrl+с")
        await pilot.pause()
        assert cancel_token.is_set()


@pytest.mark.asyncio
async def test_enter_on_welcome_advances_to_provider() -> None:
    """Start button on Welcome advances to Provider step."""
    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_for_screen(app, "WizardScreen")
        wizard = app.screen
        await pilot.pause()
        assert wizard.current_index == 0
        from app.interfaces.tui.steps.welcome import WelcomeStep

        welcome = wizard._step_cache[0]
        assert isinstance(welcome, WelcomeStep)
        welcome.query_one("#start-btn").press()
        await pilot.pause()
        assert wizard.current_index == 1


def test_ollama_model_options_use_session_cache() -> None:
    """Ollama model select must use cached local models, not an empty list."""
    from app.infrastructure.providers.model_list import _model_cache, clear_model_cache, get_cached_models
    from app.interfaces.tui.steps.provider import ProviderStep

    clear_model_cache()
    _model_cache["ollama"] = ["ollama/translategemma:12b", "ollama/llama3"]

    step = ProviderStep()
    options = step._build_model_options("ollama", live_models=get_cached_models("ollama"))
    values = [value for _, value in options]
    assert "ollama/translategemma:12b" in values
    assert "ollama/llama3" in values


@pytest.mark.asyncio
async def test_paths_rejects_missing_mods_folder(tmp_path: Path) -> None:
    """Paths step blocks advance when mods folder does not exist."""
    from app.interfaces.tui.steps.paths import PathsStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 30)) as pilot:
        step = PathsStep()
        step.initial_source = "en_US"
        step.initial_target = "uk_UA"
        step.initial_mods_path = str(tmp_path / "nonexistent")
        await app.mount(step)
        await pilot.pause()

        step.query_one("#next-btn").press()
        await pilot.pause()

        error = step.query_one("#paths-error")
        assert "⚠" in str(error.content)


@pytest.mark.asyncio
async def test_locale_switch_updates_start_button() -> None:
    """Switching locale on Welcome updates the start button label."""
    from app.interfaces.tui.steps.welcome import WelcomeStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 24)) as pilot:
        step = WelcomeStep()
        app.wizard_state.ui_locale = "uk"
        await app.mount(step)
        await pilot.pause()
        step.apply_locale()
        await pilot.pause()
        btn = step.query_one("#start-btn")
        assert "Почати" in str(btn.label)


@pytest.mark.asyncio
async def test_mods_list_fills_available_height() -> None:
    """Mods step wraps SelectionList in a flex-grow container."""
    from app.interfaces.tui.steps.mods import ModsStep
    from textual.widgets import SelectionList

    app = TranslationApp(debug=True)
    async with app.run_test(size=(100, 40)) as pilot:
        step = ModsStep()
        await app.mount(step)
        await pilot.pause()
        wrap = step.query_one("#mods-list-wrap")
        slist = wrap.query_one("#mods-list", SelectionList)
        assert slist is not None


@pytest.mark.asyncio
async def test_mods_blocks_zero_selection() -> None:
    """Mods step shows error when no mods are selected."""
    from app.core.mod_scanner import ModInfo
    from app.interfaces.tui.steps.mods import ModsStep

    app = TranslationApp(debug=True)
    async with app.run_test(size=(80, 30)) as pilot:
        app.wizard_state.mod_infos = [
            ModInfo(
                jar_path=Path("a.jar"),
                name="a.jar",
                size_bytes=100,
                has_lang_files=True,
                lang_file_count=1,
                mcfunction_count=0,
                estimated_entries=5,
                selected=True,
            )
        ]
        step = ModsStep()
        await app.mount(step)
        step.refresh_mods()
        step.query_one("#deselect-all-btn").press()
        await pilot.pause()
        step.query_one("#next-btn").press()
        await pilot.pause()
        error = step.query_one("#mods-error")
        assert "⚠" in str(error.content)


@pytest.mark.asyncio
async def test_summary_step_shows_stats() -> None:
    """SummaryStep renders with dummy stats."""
    from app.domain.stats import FileStats, ModStats, OverallStats

    stats = OverallStats()
    stats.start()
    mod_stats = ModStats(name="test_mod.jar")
    mod_stats.start()
    mod_stats.files.append(FileStats(path="en_US.json", file_type="json", entries_total=10, entries_translated=10))
    mod_stats.finish()
    stats.mods.append(mod_stats)
    stats.finish()
    stats.provider = "google"
    stats.source_lang = "en_US"
    stats.target_lang = "uk_UA"

    from app.interfaces.tui.steps.summary import SummaryStep

    step = SummaryStep()
    step.set_stats(stats)
    # Stats stored correctly even without DOM
    assert step._stats is not None
    assert step._stats.translated_mods == 1
    assert step._stats.translated_entries == 10
