from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str | None = None


class BaseLLM:
    provider: str = "base"

    async def complete(self, prompt: str) -> LLMResult:
        raise NotImplementedError

