from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


@dataclass(frozen=True)
class BotConfig:
    token: str
    api_base_url: str


def _cfg() -> BotConfig:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    api_base = (os.getenv("BRAIN_API_BASE_URL") or "http://localhost:8000").strip().rstrip("/")
    return BotConfig(token=token, api_base_url=api_base)


HELP = """\
<b>Universal AI Interface Bot</b>

Send any message to query the brain.

Commands:
- /start — welcome
- /help — this help
- /generate &lt;spec&gt; — generate files (returns JSON)

Backend API:
- /v1/query
- /v1/generate
"""


async def _post_json(url: str, payload: dict) -> dict:
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
    data = await _post_json(
        f"{cfg.api_base_url}/v1/generate",
        {"prompt": spec[1].strip(), "max_files": 5},
    )
    await msg.reply_text(
        f"Provider: {data.get('provider')}  Model: {data.get('model')}\n\n{data}",
        disable_web_page_preview=True,
    )  # type: ignore[union-attr]


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message  # type: ignore[assignment]
    text = (msg.text or "").strip()
    if not text:
        return

    cfg = _cfg()
    data = await _post_json(
        f"{cfg.api_base_url}/v1/query",
        {"q": text, "mode": "query", "top_k": 5},
    )
    answer = (data.get("answer") or "").strip()
    provider = data.get("provider")
    model = data.get("model") or "n/a"
    out = f"{answer}\n\n— {provider} / {model}"
    await msg.reply_text(out, disable_web_page_preview=True)  # type: ignore[union-attr]


def main() -> None:
    cfg = _cfg()
    app = Application.builder().token(cfg.token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Long polling (simplest). For scale, run as multiple workers with webhooks.
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()

