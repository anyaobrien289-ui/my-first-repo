from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .brain.engine import BrainEngine
from .core.config import settings
from .core.models import (
    GenerateRequest,
    GenerateResponse,
    IndexRequest,
    IndexResponse,
    QueryRequest,
    QueryResponse,
    SearchRequest,
    SearchResponse,
)
from .llm.factory import get_llm
from .memory.store import InMemoryBM25

app = FastAPI(title="Universal AI Interface", version="0.1.0")

# Serve the browser UI from the repo's /frontend folder (if present),
# so users can just open http://localhost:8000/ and see the search box.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_DIR = _REPO_ROOT / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="ui")

origins = ["*"]
if settings.cors_allow_origins and settings.cors_allow_origins != "*":
    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = InMemoryBM25()


def _engine() -> BrainEngine:
    llm = get_llm()
    return BrainEngine(llm=llm, memory=memory)


@app.get("/")
async def root():
    # Prefer redirecting to the mounted static UI to avoid edge cases with
    # reverse proxies/content-types/caching.
    if _FRONTEND_DIR.exists():
        return RedirectResponse(url="/ui/")
    index = _FRONTEND_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="UI not found (missing frontend/index.html)")
    return FileResponse(str(index))


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/index", response_model=IndexResponse)
async def index(req: IndexRequest) -> IndexResponse:
    if len(req.text) > settings.max_index_chars:
        raise HTTPException(status_code=413, detail="Document too large")
    doc_id = memory.index(text=req.text, metadata=req.metadata, id=req.id)
    return IndexResponse(id=doc_id)


@app.post("/v1/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    matches = memory.search(req.q, k=req.k)
    return SearchResponse(matches=matches)


@app.post("/v1/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    engine = _engine()
    answer, sources = await engine.answer(req.q, top_k=req.top_k)
    return QueryResponse(
        answer=answer,
        provider=engine.llm.provider,
        model=getattr(engine.llm, "_model", None) or getattr(engine.llm, "_model_id", None),
        sources=sources,
    )


@app.post("/v1/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    engine = _engine()
    files = await engine.generate_files(req.prompt, max_files=req.max_files)
    return GenerateResponse(
        files=files, provider=engine.llm.provider, model=getattr(engine.llm, "_model", None)
    )

