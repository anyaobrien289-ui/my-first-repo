from __future__ import annotations

from .base import BaseLLM, LLMResult
from ..core.config import settings


class TransformersLocalLLM(BaseLLM):
    """
    Optional local HF Transformers adapter.

    This module intentionally imports heavy deps lazily so the base install works
    without GPU/torch/transformers.
    """

    provider = "transformers"

    def __init__(self) -> None:
        self._model_id = settings.brain_model

        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "TransformersLocalLLM requires optional deps: torch, transformers"
            ) from e

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_id)

        # GPU acceleration if available; otherwise CPU.
        if torch.cuda.is_available():
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_id, device_map="auto"
            )
        else:
            self._model = AutoModelForCausalLM.from_pretrained(self._model_id)

        self._model.eval()

    async def complete(self, prompt: str) -> LLMResult:
        torch = self._torch
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
            )
        text = self._tokenizer.decode(out[0], skip_special_tokens=True)
        # Return only the completion-ish tail when possible.
        if text.startswith(prompt):
            text = text[len(prompt) :].lstrip()
        return LLMResult(text=text, model=self._model_id)

