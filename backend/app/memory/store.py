from __future__ import annotations

import math
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class Doc:
    id: str
    text: str
    metadata: dict[str, Any]


class InMemoryBM25:
    """
    Minimal BM25 memory store to avoid heavy deps.

    This is intentionally simple: single-process, good for demos and tests.
    Replace with a real search/vector DB for production scale.
    """

    def __init__(self) -> None:
        self._docs: dict[str, Doc] = {}
        self._doc_len: dict[str, int] = {}
        self._tf: dict[str, Counter[str]] = {}
        self._df: Counter[str] = Counter()
        self._avgdl: float = 0.0

    def index(self, text: str, metadata: dict[str, Any] | None = None, id: str | None = None) -> str:
        doc_id = id or str(uuid.uuid4())
        md = dict(metadata or {})

        # Remove existing (reindex).
        if doc_id in self._docs:
            self.delete(doc_id)

        tokens = _tokenize(text)
        tf = Counter(tokens)
        self._docs[doc_id] = Doc(id=doc_id, text=text, metadata=md)
        self._tf[doc_id] = tf
        self._doc_len[doc_id] = len(tokens)
        for term in set(tokens):
            self._df[term] += 1

        self._recompute_avgdl()
        return doc_id

    def delete(self, doc_id: str) -> None:
        doc = self._docs.pop(doc_id, None)
        if not doc:
            return
        tf = self._tf.pop(doc_id, Counter())
        self._doc_len.pop(doc_id, None)
        for term in set(tf.keys()):
            self._df[term] -= 1
            if self._df[term] <= 0:
                del self._df[term]
        self._recompute_avgdl()

    def _recompute_avgdl(self) -> None:
        n = len(self._doc_len)
        self._avgdl = (sum(self._doc_len.values()) / n) if n else 0.0

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        q_terms = _tokenize(query)
        if not q_terms or not self._docs:
            return []

        N = len(self._docs)
        k1 = 1.5
        b = 0.75
        avgdl = self._avgdl or 1.0

        # Precompute IDF
        idf: dict[str, float] = {}
        for t in set(q_terms):
            df = self._df.get(t, 0)
            # BM25+ style smoothing.
            idf[t] = math.log(1.0 + (N - df + 0.5) / (df + 0.5)) if df else 0.0

        scores: dict[str, float] = defaultdict(float)
        for doc_id, tf in self._tf.items():
            dl = self._doc_len.get(doc_id, 0) or 1
            denom_const = k1 * (1.0 - b + b * (dl / avgdl))
            s = 0.0
            for t in q_terms:
                f = tf.get(t, 0)
                if not f:
                    continue
                s += idf.get(t, 0.0) * (f * (k1 + 1.0)) / (f + denom_const)
            if s:
                scores[doc_id] = s

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[: max(0, k)]
        out: list[dict[str, Any]] = []
        for doc_id, score in ranked:
            d = self._docs[doc_id]
            out.append(
                {
                    "id": d.id,
                    "score": score,
                    "metadata": d.metadata,
                    "snippet": d.text[:500],
                }
            )
        return out

