from __future__ import annotations

from ..core.config import settings
from .base import BaseLLM
from .stub import StubLLM


def get_llm() -> BaseLLM:
    provider = (settings.brain_llm_provider or "stub").lower().strip()

    if provider == "stub":
        return StubLLM()

    if provider == "openai":
        from .openai_compat import OpenAICompatLLM

        return OpenAICompatLLM()

    if provider == "transformers":
        from .transformers_local import TransformersLocalLLM

        return TransformersLocalLLM()

    raise RuntimeError(f"Unknown BRAIN_LLM_PROVIDER: {settings.brain_llm_provider!r}")

