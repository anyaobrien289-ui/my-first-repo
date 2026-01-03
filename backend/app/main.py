from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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

_EMBEDDED_UI_HTML = r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Universal AI Interface</title>
    <style>
      :root { --bg:#0b0f17; --muted:#94a3b8; --text:#e5e7eb; --border:#243244; --accent:#60a5fa; }
      body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
             background: radial-gradient(1200px 700px at 20% 0%, #111c33, var(--bg)); color: var(--text); }
      .wrap { max-width: 980px; margin: 0 auto; padding: 48px 20px; }
      .title { font-size: 20px; letter-spacing: 0.3px; color: var(--muted); }
      .hero { margin-top: 10px; font-size: 36px; font-weight: 700; }
      .hint { margin-top: 10px; color: var(--muted); font-size: 14px; }
      .bar { margin-top: 18px; display:grid; grid-template-columns: 160px 1fr 120px; gap:10px;
             background: rgba(17,24,39,0.85); border:1px solid var(--border); padding:12px; border-radius:14px; }
      select, input, button { border-radius: 10px; border:1px solid var(--border); background:#0b1220; color:var(--text);
                              padding: 12px; font-size: 14px; outline:none; }
      input { width: 100%; }
      button { background: linear-gradient(180deg, #2563eb, #1d4ed8); border: 1px solid #1e40af; cursor:pointer; font-weight:600; }
      button:disabled { opacity: 0.6; cursor:not-allowed; }
      .grid { margin-top: 18px; display:grid; grid-template-columns: 1fr; gap: 12px; }
      .card { background: rgba(17,24,39,0.7); border:1px solid var(--border); border-radius:14px; padding: 14px; }
      .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
      .pill { display:inline-flex; border:1px solid var(--border); border-radius:999px; padding:6px 10px; font-size:12px;
              color: var(--muted); background: rgba(11,18,32,0.6); }
      pre { margin: 10px 0 0; padding: 12px; border-radius: 12px; background: #0b1220; border:1px solid var(--border);
            overflow:auto; white-space: pre-wrap; word-break: break-word; }
      a { color: var(--accent); }

      /* Mobile: make the search box big and obvious */
      @media (max-width: 640px) {
        .wrap { padding: 24px 14px; }
        .hero { font-size: 30px; }
        .bar { grid-template-columns: 1fr; }
        select, input, button { font-size: 16px; padding: 14px; } /* iOS tap-friendly */
        .hint { font-size: 15px; }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="title">Universal Search Interface</div>
      <div class="hero">Ask. Create. Generate.</div>
      <div class="hint"><strong style="color:#e5e7eb">Ask a question:</strong> type below and press <strong>Enter</strong> or click <strong>Go</strong>.</div>

      <div class="bar">
        <select id="mode">
          <option value="query">Query (answer using memory)</option>
          <option value="search">Search memory (BM25)</option>
          <option value="generate">Generate files (JSON)</option>
          <option value="index">Index memory (store text)</option>
        </select>
        <input id="q" placeholder="Try: Index: The capital of France is Paris" />
        <button id="go">Go</button>
      </div>

      <div class="grid">
        <div class="card">
          <div class="row">
            <span class="pill">API</span>
            <span style="color: var(--muted)">This UI calls the API on the same host.</span>
            <a href="/docs" target="_blank" rel="noopener noreferrer">Docs</a>
            <a href="/healthz" target="_blank" rel="noopener noreferrer">Health</a>
          </div>
        </div>
        <div class="card">
          <div class="row">
            <span class="pill">Output</span>
            <span class="pill" id="meta" style="display:none"></span>
          </div>
          <pre id="out">Ready.</pre>
        </div>
      </div>
    </div>

    <script>
      const $ = (id) => document.getElementById(id);
      const pretty = (x) => JSON.stringify(x, null, 2);
      async function post(url, body) {
        const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const txt = await r.text();
        let data = null;
        try { data = JSON.parse(txt); } catch { data = { raw: txt }; }
        if (!r.ok) throw new Error(`${r.status}: ${pretty(data)}`);
        return data;
      }
      async function run() {
        const mode = $("mode").value;
        const q = $("q").value.trim();
        $("meta").style.display = "none";
        $("meta").textContent = "";
        if (!q) return;
        $("go").disabled = true;
        $("out").textContent = "Working...";
        try {
          if (mode === "index") {
            const text = q.startsWith("Index:") ? q.slice("Index:".length).trim() : q;
            const data = await post(`/v1/index`, { text, metadata: { via: "ui" } });
            $("meta").style.display = "inline-flex";
            $("meta").textContent = `indexed id=${data.id}`;
            $("out").textContent = pretty(data);
          } else if (mode === "search") {
            const data = await post(`/v1/search`, { q, k: 5 });
            $("out").textContent = pretty(data);
          } else if (mode === "generate") {
            const data = await post(`/v1/generate`, { prompt: q, max_files: 5 });
            $("meta").style.display = "inline-flex";
            $("meta").textContent = `provider=${data.provider} model=${data.model || "n/a"}`;
            $("out").textContent = pretty(data);
          } else {
            const data = await post(`/v1/query`, { q, mode: "query", top_k: 5 });
            $("meta").style.display = "inline-flex";
            $("meta").textContent = `provider=${data.provider} model=${data.model || "n/a"}`;
            $("out").textContent = pretty(data);
          }
        } catch (e) {
          $("out").textContent = String(e);
        } finally {
          $("go").disabled = false;
        }
      }
      $("go").addEventListener("click", run);
      $("q").addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
    </script>
  </body>
</html>
""".strip()

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
async def root(request: Request):
    """
    Landing page that provides a clickable absolute URL to the UI.

    In remote workspaces, users often can't use localhost directly; this page
    builds links from the incoming Host so it's always clickable.
    """
    base = str(request.base_url).rstrip("/")
    ui_url = f"{base}/ui/"
    docs_url = f"{base}/docs"
    health_url = f"{base}/healthz"

    if _FRONTEND_DIR.exists():
        return HTMLResponse(
            f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Universal AI Interface</title>
    <style>
      body {{
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
        background: #0b0f17;
        color: #e5e7eb;
        margin: 0;
        padding: 40px 18px;
      }}
      .wrap {{ max-width: 880px; margin: 0 auto; }}
      .card {{
        background: rgba(17, 24, 39, 0.8);
        border: 1px solid #243244;
        border-radius: 14px;
        padding: 16px;
      }}
      a {{
        color: #60a5fa;
        font-weight: 700;
        text-decoration: none;
      }}
      a:hover {{ text-decoration: underline; }}
      .muted {{ color: #94a3b8; }}
      code {{
        background: #0b1220;
        border: 1px solid #243244;
        padding: 3px 6px;
        border-radius: 8px;
      }}
      .links {{ display: grid; gap: 10px; margin-top: 12px; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <h2>Universal AI Interface</h2>
      <div class="card">
        <div class="muted">Click to view your creation:</div>
        <div class="links">
          <div><a href="{base}/panel/">Open the search panel</a> <span class="muted">(best on iPhone)</span></div>
          <div><a href="{ui_url}">Open the UI search box</a> <span class="muted">(/ui/)</span></div>
          <div><a href="{docs_url}">Open API docs</a> <span class="muted">(/docs)</span></div>
          <div><a href="{health_url}">Open health check</a> <span class="muted">(/healthz)</span></div>
        </div>
        <div class="muted" style="margin-top: 14px;">
          If you still can’t reach this, make sure you’re using the environment’s forwarded/preview URL (not your laptop’s <code>localhost</code>).
        </div>
      </div>
    </div>
  </body>
</html>
            """.strip()
        )

    # Prefer redirecting to the mounted static UI to avoid edge cases with
    # reverse proxies/content-types/caching.
    if _FRONTEND_DIR.exists():
        return RedirectResponse(url="/ui/")
    index = _FRONTEND_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="UI not found (missing frontend/index.html)")
    return FileResponse(str(index))


@app.get("/ui/", response_class=HTMLResponse)
@app.get("/ui/index.html", response_class=HTMLResponse)
async def ui_fallback() -> HTMLResponse:
    """
    Embedded UI fallback.

    If the StaticFiles mount is active, Starlette will usually serve /ui/ before
    this route. If it isn't (or in some environments where static mounting
    behaves oddly), this guarantees /ui/ still works.
    """
    # If the file exists, prefer serving it for easier editing.
    index = _FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse(_EMBEDDED_UI_HTML)


@app.get("/panel/", response_class=HTMLResponse)
async def panel() -> HTMLResponse:
    """
    A dedicated "panel" URL for mobile users.
    Always serves the embedded UI (or frontend/index.html if present).
    """
    index = _FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse(_EMBEDDED_UI_HTML)


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

