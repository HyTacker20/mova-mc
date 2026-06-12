"""LiteLLM transport — uses the litellm package (sync + async)."""

from __future__ import annotations

from ....core.dotenv_loader import load_dotenv_files
from ..reasoning_models import ReasoningTask, build_extra_body, scale_max_tokens
from ._response import extract_content


class LitellmTransport:
    def __init__(
        self,
        model: str,
        *,
        task: ReasoningTask = ReasoningTask.TRANSLATE,
    ) -> None:
        load_dotenv_files()
        from litellm import acompletion, completion

        self._completion = completion
        self._acompletion = acompletion
        self._model = model
        self._task = task
        self._extra_body = build_extra_body(model, task=task)

    def _completion_kwargs(
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
        scaled = scale_max_tokens(self._model, max_tokens, task=self._task)
        response = self._completion(**self._completion_kwargs(messages, temperature, scaled))
        return extract_content(response, transport=type(self).__name__)

    async def acomplete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        scaled = scale_max_tokens(self._model, max_tokens, task=self._task)
        response = await self._acompletion(**self._completion_kwargs(messages, temperature, scaled))
        return extract_content(response, transport=type(self).__name__)
