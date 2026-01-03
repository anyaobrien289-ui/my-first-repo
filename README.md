## Universal AI Interface (GPU-capable “Artificial Brain” MVP)

This repository provides a **universal search-style interface** (web + API) that lets users **query, index knowledge, search memory, and generate artifacts** via natural language.

It is designed as a **modular “brain”**:
- **Interface layer**: a single universal endpoint surface (`/v1/query`, `/v1/search`, `/v1/index`, `/v1/generate`)
- **Cognition layer**: pluggable LLM adapters (OpenAI-compatible, local stub, optional local GPU model)
- **Memory layer**: lightweight local document store + BM25 ranking (optional embeddings later)
- **Scalability shape**: stateless API nodes, externalized memory store, horizontally scalable model workers

### Quickstart

#### Backend (API)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Then open the UI at:
- `http://localhost:8000/panel/` (best on mobile)
- `http://localhost:8000/ui/` (desktop UI)
- `http://localhost:8000/` (landing page with links)

> On iPhone, `localhost` refers to the phone. Use a forwarded/public URL (remote workspace) or your computer’s LAN IP (same Wi‑Fi).

#### Configuration (LLM provider)

The backend supports multiple providers selected via environment variables:

- **Stub provider (default)**: always available, no credentials. Useful for smoke-testing.
  - `BRAIN_LLM_PROVIDER=stub`
- **OpenAI-compatible** (recommended if you have a key):
  - `BRAIN_LLM_PROVIDER=openai`
  - `OPENAI_API_KEY=...`
  - `OPENAI_BASE_URL=...` (optional; use for OpenAI-compatible gateways)
  - `BRAIN_MODEL=...` (optional)
- **Local GPU/CPU Transformers** (optional extra; requires heavier deps):
  - `BRAIN_LLM_PROVIDER=transformers`
  - `BRAIN_MODEL=...` (e.g. a local HF model id)

### What “unlimited scalability” means here

No single repo can ship literal infinite compute. This implementation is **architected for scale**:
- **Stateless API**: run many replicas behind a load balancer.
- **External memory**: swap the included in-process store for Redis/Postgres/Vector DB.
- **Model workers**: run GPU inference with a dedicated engine (e.g. vLLM/TGI) and point the adapter at it.

### API surface (stable)

- `POST /v1/query` — natural language question/command → answer
- `POST /v1/index` — add text to “brain memory”
- `POST /v1/search` — search memory (BM25)
- `POST /v1/generate` — generate “artifacts” (returns files as `{path, content}`)

### Telegram bot (optional)

This repo includes a Telegram bot that forwards messages to the API.

1) Install bot deps:

```bash
pip install -r backend/requirements-bot.txt
```

2) Set env vars (do **not** commit your token):

```bash
export TELEGRAM_BOT_TOKEN="...your token..."
export BRAIN_API_BASE_URL="http://localhost:8000"
```

3) Run the bot:

```bash
python3 backend/bot/telegram_bot.py
```

### Safety note

This is a general-purpose generation interface. If you connect a powerful model, you should add:
- auth, rate limiting, audit logs
- sandboxing for any code execution (this repo does **not** execute generated code)
- content filtering policies as needed