"""LiteLLM transport — uses the litellm package (sync + async)."""

from __future__ import annotations

from ....core.dotenv_loader import load_dotenv_files
from ._response import extract_content


class LitellmTransport:
    def __init__(self, model: str) -> None:
        load_dotenv_files()
        from litellm import acompletion, completion

        self._completion = completion
        self._acompletion = acompletion
        self._model = model

    def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        response = self._completion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return extract_content(response, transport=type(self).__name__)

    async def acomplete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        response = await self._acompletion(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return extract_content(response, transport=type(self).__name__)
