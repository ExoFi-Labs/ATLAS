from __future__ import annotations

from typing import AsyncIterator

from openai import AsyncOpenAI

from atlas.config import LLMSettings
from atlas.providers.base import ChatMessage


class OpenAICompatLLM:
    """
    Single LLM adapter for Ollama, vLLM, and any OpenAI-compatible server.

    Home:  ATLAS_LLM__BASE_URL=http://host.docker.internal:11434/v1  (Ollama)
    Work:  ATLAS_LLM__BASE_URL=http://vllm:8000/v1                  (vLLM)
    """

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key or "not-needed",
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        payload = [{"role": message.role, "content": message.content} for message in messages]

        if stream:
            return self._stream(payload)

        response = await self._client.chat.completions.create(
            model=self.settings.model,
            messages=payload,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            stream=False,
        )
        return response.choices[0].message.content or ""

    async def _stream(self, payload: list[dict[str, str]]) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.settings.model,
            messages=payload,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
