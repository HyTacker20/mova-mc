"""Tests for Workspace context manager."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.filesystem.workspace import Workspace


class TestWorkspace:
    def test_creates_and_cleans_up(self, tmp_path: Path) -> None:
        """Workspace creates the directory on enter and removes it on exit."""
        ws_path = tmp_path / "ws"
        assert not ws_path.exists()

        with Workspace(str(ws_path)) as returned:
            assert ws_path.exists()
            assert returned == ws_path
            # Create a file inside to verify it gets cleaned up
            (ws_path / "test.txt").write_text("hello")

        assert not ws_path.exists()

    def test_workspace_with_existing_dir(self, tmp_path: Path) -> None:
        """Workspace handles already-existing directory (mkdir exist_ok)."""
        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        (ws_path / "pre_existing.txt").write_text("before")

        with Workspace(str(ws_path)):
            assert ws_path.exists()
            assert (ws_path / "pre_existing.txt").exists()

        assert not ws_path.exists()

    def test_workspace_cleanup_after_exception(self, tmp_path: Path) -> None:
        """Workspace cleans up even when an exception occurs inside the block."""
        ws_path = tmp_path / "ws"

        try:
            with Workspace(str(ws_path)):
                assert ws_path.exists()
                raise ValueError("something went wrong")
        except ValueError:
            pass

        assert not ws_path.exists()

    def test_multiple_workspaces(self, tmp_path: Path) -> None:
        """Multiple Workspace instances work independently."""
        ws1 = tmp_path / "ws1"
        ws2 = tmp_path / "ws2"

        with Workspace(str(ws1)) as r1:
            with Workspace(str(ws2)) as r2:
                assert r1 == ws1
                assert r2 == ws2
                assert ws1.exists()
                assert ws2.exists()
            assert not ws2.exists()
            assert ws1.exists()
        assert not ws1.exists()
