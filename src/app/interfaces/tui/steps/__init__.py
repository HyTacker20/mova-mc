"""Step widgets for the translation wizard — common messages."""

from __future__ import annotations

from textual.message import Message


class StepComplete(Message):
    """Emitted by a step when the user wants to advance."""

    def __init__(self, data: dict | None = None) -> None:
        self.data = data
        super().__init__()


class StepBack(Message):
    """Emitted by a step when the user wants to go back."""


class StepCancel(Message):
    """Emitted by a step when the user wants to quit."""
