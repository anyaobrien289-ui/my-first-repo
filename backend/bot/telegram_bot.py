from __future__ import annotations

import os
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from backend.app.brain.engine import BrainEngine
from backend.app.llm.factory import get_llm
from backend.app.memory.store import InMemoryBM25


@dataclass(frozen=True)
class BotConfig:
    token: str
    mode: str  # local | http
    api_base_url: str | None = None


def _cfg() -> BotConfig:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    api_base = (os.getenv("BRAIN_API_BASE_URL") or "").strip().rstrip("/")
    # If you set BRAIN_API_BASE_URL, bot will call the API over HTTP.
    # Otherwise it will run the BrainEngine locally (no URL required).
    if api_base:
        return BotConfig(token=token, mode="http", api_base_url=api_base)
    return BotConfig(token=token, mode="local", api_base_url=None)


HELP = """\
<b>Universal AI Interface Bot</b>

Send any message to query the brain.

Commands:
- /start — welcome
- /help — this help
- /generate &lt;spec&gt; — generate files (returns JSON)
- /index &lt;text&gt; — add memory
- /search &lt;q&gt; — search memory

Backend API:
- /v1/query
- /v1/generate
"""

_memory = InMemoryBM25()


def _engine() -> BrainEngine:
    # Local engine (in-process). Memory is in-memory (resets on restart).
    return BrainEngine(llm=get_llm(), memory=_memory)


async def _http_post_json(url: str, payload: dict) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode=ParseMode.HTML)  # type: ignore[union-attr]


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode=ParseMode.HTML)  # type: ignore[union-attr]


async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message  # type: ignore[assignment]
    spec = (msg.text or "").split(" ", 1)
    if len(spec) < 2 or not spec[1].strip():
        await msg.reply_text("Usage: /generate <what to generate>")  # type: ignore[union-attr]
        return

    cfg = _cfg()
    if cfg.mode == "http":
        data = await _http_post_json(
            f"{cfg.api_base_url}/v1/generate",  # type: ignore[operator]
            {"prompt": spec[1].strip(), "max_files": 5},
        )
        await msg.reply_text(
            f"Provider: {data.get('provider')}  Model: {data.get('model')}\n\n{data}",
            disable_web_page_preview=True,
        )  # type: ignore[union-attr]
        return

    engine = _engine()
    files = await engine.generate_files(spec[1].strip(), max_files=5)
    out = {"files": files, "provider": engine.llm.provider, "model": getattr(engine.llm, "_model", None)}
    await msg.reply_text(str(out), disable_web_page_preview=True)  # type: ignore[union-attr]


async def index_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message  # type: ignore[assignment]
    parts = (msg.text or "").split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await msg.reply_text("Usage: /index <text to remember>")  # type: ignore[union-attr]
        return

    cfg = _cfg()
    text = parts[1].strip()
    if cfg.mode == "http":
        data = await _http_post_json(
            f"{cfg.api_base_url}/v1/index",  # type: ignore[operator]
            {"text": text, "metadata": {"via": "telegram"}},
        )
        await msg.reply_text(f"Indexed id={data.get('id')}")  # type: ignore[union-attr]
        return

    doc_id = _memory.index(text=text, metadata={"via": "telegram"})
    await msg.reply_text(f"Indexed id={doc_id}")  # type: ignore[union-attr]


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message  # type: ignore[assignment]
    parts = (msg.text or "").split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await msg.reply_text("Usage: /search <query>")  # type: ignore[union-attr]
        return

    cfg = _cfg()
    q = parts[1].strip()
    if cfg.mode == "http":
        data = await _http_post_json(
            f"{cfg.api_base_url}/v1/search",  # type: ignore[operator]
            {"q": q, "k": 5},
        )
        await msg.reply_text(str(data), disable_web_page_preview=True)  # type: ignore[union-attr]
        return

    matches = _memory.search(q, k=5)
    await msg.reply_text(str({"matches": matches}), disable_web_page_preview=True)  # type: ignore[union-attr]


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message  # type: ignore[assignment]
    text = (msg.text or "").strip()
    if not text:
        return

    cfg = _cfg()
    if cfg.mode == "http":
        data = await _http_post_json(
            f"{cfg.api_base_url}/v1/query",  # type: ignore[operator]
            {"q": text, "mode": "query", "top_k": 5},
        )
        answer = (data.get("answer") or "").strip()
        provider = data.get("provider")
        model = data.get("model") or "n/a"
        out = f"{answer}\n\n— {provider} / {model}"
        await msg.reply_text(out, disable_web_page_preview=True)  # type: ignore[union-attr]
        return

    engine = _engine()
    answer, _sources = await engine.answer(text, top_k=5)
    out = f"{answer}\n\n— {engine.llm.provider}"
    await msg.reply_text(out, disable_web_page_preview=True)  # type: ignore[union-attr]


def main() -> None:
    cfg = _cfg()
    app = Application.builder().token(cfg.token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(CommandHandler("index", index_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Long polling (simplest). For scale, run as multiple workers with webhooks.
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()

