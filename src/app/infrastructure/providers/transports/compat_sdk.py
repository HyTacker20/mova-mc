"""OpenAI-compatible transport — for any OpenAI-compatible API (sync + async)."""

from __future__ import annotations

import os

from ....core.dotenv_loader import load_dotenv_files
from ._response import extract_content


class OpenAICompatTransport:
    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        extra_body: dict | None = None,
        api_key_env: tuple[str, ...] = ("OPENAICOMPATIBLE_API_KEY", "OPENAI_API_KEY"),
        missing_key_message: str = "OPENAICOMPATIBLE_API_KEY environment variable not set.",
    ) -> None:
        load_dotenv_files()
        from openai import AsyncOpenAI, OpenAI

        resolved_key = api_key
        if not resolved_key:
            for env_name in api_key_env:
                resolved_key = os.getenv(env_name)
                if resolved_key:
                    break
        if not resolved_key:
            raise ValueError(missing_key_message)

        client_kwargs: dict = {"api_key": resolved_key}
        if base_url is not None:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(**client_kwargs)
        self._async_client = AsyncOpenAI(**client_kwargs)
        self._model = model
        self._extra_body = extra_body

    def _create_kwargs(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._extra_body:
            kwargs["extra_body"] = self._extra_body
        return kwargs

    def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        completion = self._client.chat.completions.create(**self._create_kwargs(messages, temperature, max_tokens))
        return extract_content(completion, transport=type(self).__name__)

    async def acomplete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        completion = await self._async_client.chat.completions.create(
            **self._create_kwargs(messages, temperature, max_tokens)
        )
        return extract_content(completion, transport=type(self).__name__)
