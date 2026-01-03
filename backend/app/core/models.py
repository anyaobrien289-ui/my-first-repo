from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    q: str = Field(..., description="Natural language query or command")
    mode: Literal["query", "create", "search", "generate"] = "query"
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    provider: str
    model: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)


class IndexRequest(BaseModel):
    id: str | None = Field(default=None, description="Optional client-provided id")
    text: str = Field(..., description="Text to store in memory")
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexResponse(BaseModel):
    id: str


class SearchRequest(BaseModel):
    q: str
    k: int = 5


class SearchResponse(BaseModel):
    matches: list[dict[str, Any]]


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Natural language spec describing what to generate")
    max_files: int = 5


class GeneratedFile(BaseModel):
    path: str
    content: str


class GenerateResponse(BaseModel):
    files: list[GeneratedFile]
    provider: str
    model: str | None = None

