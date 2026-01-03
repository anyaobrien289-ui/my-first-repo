from __future__ import annotations

import json
from typing import Any

from ..llm.base import BaseLLM
from ..memory.store import InMemoryBM25


class BrainEngine:
    """
    Orchestrates:
    - memory retrieval
    - LLM prompting
    - simple artifact generation format
    """

    def __init__(self, llm: BaseLLM, memory: InMemoryBM25) -> None:
        self.llm = llm
        self.memory = memory

    async def answer(self, q: str, top_k: int = 5) -> tuple[str, list[dict[str, Any]]]:
        matches = self.memory.search(q, k=top_k)
        context = ""
        if matches:
            context = "\n\n".join(
                [f"[{i+1}] {m['snippet']}" for i, m in enumerate(matches)]
            )

        prompt = (
            "You are a universal AI 'brain'.\n"
            "Use the provided memory snippets if relevant.\n\n"
            f"MEMORY:\n{context}\n\n"
            f"USER:\n{q}\n\n"
            "ASSISTANT:"
        )
        res = await self.llm.complete(prompt)
        return res.text.strip(), matches

    async def generate_files(self, prompt: str, max_files: int = 5) -> list[dict[str, str]]:
        """
        Ask the model to return a JSON object: {"files":[{"path":"...","content":"..."}]}.
        If parsing fails, fall back to a single file.
        """

        schema = {
            "files": [
                {"path": "README.md", "content": "..."},  # example
            ]
        }
        system = (
            "Generate project artifacts as strict JSON only.\n"
            f"Return a JSON object like: {json.dumps(schema)}\n"
            f"Constraints: at most {max_files} files; keep paths relative; no binaries.\n"
        )
        full = f"{system}\nUSER_SPEC:\n{prompt}\n\nJSON:"
        res = await self.llm.complete(full)
        text = res.text.strip()

        try:
            data = json.loads(text)
            files = data.get("files", [])
            out: list[dict[str, str]] = []
            for f in files[: max_files]:
                p = str(f.get("path", "")).strip()
                c = str(f.get("content", ""))
                if not p:
                    continue
                out.append({"path": p, "content": c})
            if out:
                return out
        except Exception:
            pass

        return [{"path": "GENERATED.txt", "content": text[:20000]}]

