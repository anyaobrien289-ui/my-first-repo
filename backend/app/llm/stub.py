from __future__ import annotations

import textwrap

from .base import BaseLLM, LLMResult


class StubLLM(BaseLLM):
    """
    Deterministic stub model for smoke tests and local dev.
    """

    provider = "stub"

    async def complete(self, prompt: str) -> LLMResult:
        p = prompt.strip()
        response = textwrap.dedent(
            f"""
            (stub) I received your request and would route it to the configured model.

            Request:
            {p[:2000]}

            Notes:
            - Set BRAIN_LLM_PROVIDER=openai and OPENAI_API_KEY to use a real model.
            - Or install transformers/torch and use BRAIN_LLM_PROVIDER=transformers.
            """
        ).strip()
        return LLMResult(text=response, model=None)

