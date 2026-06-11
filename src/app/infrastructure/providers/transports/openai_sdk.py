"""OpenAI SDK transport — uses the official openai package (sync + async)."""

from __future__ import annotations

import os

from .compat_sdk import OpenAICompatTransport


class OpenAISDKTransport(OpenAICompatTransport):
    """Thin wrapper around :class:`OpenAICompatTransport` for the official OpenAI API."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        super().__init__(
            model=model,
            base_url=None,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            api_key_env=("OPENAI_API_KEY",),
            missing_key_message="OPENAI_API_KEY environment variable not set.",
        )
