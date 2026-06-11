"""Tests for layout-independent TUI key bindings."""

from __future__ import annotations

from app.interfaces.tui.key_bindings import layout_binding


def _binding_keys(bindings: list) -> list[str]:
    return [b.key for b in bindings]


def test_layout_binding_ctrl_c_includes_cyrillic() -> None:
    keys = _binding_keys(layout_binding("ctrl+c", "quit", show=False))
    assert keys == ["ctrl+c", "ctrl+с"]


def test_layout_binding_q_includes_cyrillic() -> None:
    keys = _binding_keys(layout_binding("q", "quit", show=False))
    assert keys == ["q", "й"]


def test_layout_binding_ctrl_l_includes_cyrillic() -> None:
    keys = _binding_keys(layout_binding("ctrl+l", "toggle_log", show=False))
    assert keys == ["ctrl+l", "ctrl+д"]


def test_layout_binding_escape_has_no_alias() -> None:
    keys = _binding_keys(layout_binding("escape", "go_back", "Back", show=True))
    assert keys == ["escape"]


def test_layout_binding_f1_has_no_alias() -> None:
    keys = _binding_keys(layout_binding("f1", "show_help", "Help", show=True))
    assert keys == ["f1"]


def test_layout_binding_preserves_action_and_show() -> None:
    bindings = layout_binding("ctrl+c", "quit_cancel", "Quit", show=False)
    assert len(bindings) == 2
    for binding in bindings:
        assert binding.action == "quit_cancel"
        assert binding.description == "Quit"
        assert binding.show is False
