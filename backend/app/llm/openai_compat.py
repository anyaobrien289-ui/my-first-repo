from __future__ import annotations

from typing import Any

import httpx

from ..core.config import settings
from .base import BaseLLM, LLMResult


class OpenAICompatLLM(BaseLLM):
    """
    Minimal OpenAI-compatible Chat Completions adapter.

    Supports:
    - OpenAI official endpoint (default base url)
    - Any OpenAI-compatible gateway (set OPENAI_BASE_URL)
    """

    provider = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for provider=openai")

        self._api_key = settings.openai_api_key
        self._base_url = (settings.openai_base_url or "https://api.openai.com").rstrip("/")
        self._model = settings.brain_model

    async def complete(self, prompt: str) -> LLMResult:
        url = f"{self._base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a universal AI interface. Be helpful and concise."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return LLMResult(text=text or "", model=self._model)

