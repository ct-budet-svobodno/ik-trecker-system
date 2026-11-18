"""Кнопки опросов трекера. Единственный polling остаётся у общего бота."""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.request

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

poll_router = Router()
logger = logging.getLogger(__name__)


def submit_vote(token: str, telegram_id: int, poll_id: int, choice: int, chat_id: int | None = None):
    raw = json.dumps(dict(telegram_id=telegram_id, poll_id=poll_id, choice=choice, chat_id=chat_id)).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(token.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    url = os.getenv("TRACKER_API_URL", "http://backend:8000").rstrip("/") + "/api/telegram-polls/vote"
    request = urllib.request.Request(url, data=raw, headers={
        "Content-Type": "application/json", "X-Poll-Time": stamp, "X-Poll-Signature": signature,
    })
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return "Ваш выбор: " + json.loads(response.read())["choice"]
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            return json.loads(exc.read()).get("detail", "Опрос закрыт")
        raise RuntimeError("Не удалось сохранить ответ") from None


@poll_router.callback_query(F.data.startswith("ikpoll:"))
async def answer_poll(query: CallbackQuery):
    if not query.message or query.message.chat.type not in ("private", "group", "supergroup") or (
        query.message.chat.type == "private" and query.message.chat.id != query.from_user.id
    ):
        await query.answer("Ответьте в исходном сообщении опроса", show_alert=True)
        return
    try:
        _, poll, choice = query.data.split(":")
        message = await asyncio.to_thread(submit_vote, query.bot.token, query.from_user.id, int(poll), int(choice), query.message.chat.id)
    except Exception:
        logger.warning("Не удалось сохранить ответ на опрос трекера")
        message = "Не удалось сохранить ответ. Нажмите кнопку ещё раз чуть позже."
    await query.answer(message[:190], show_alert=True)


@poll_router.message(Command("chatid"), F.chat.type.in_({"group", "supergroup"}))
async def show_chat_id(message: Message):
    await message.reply(
        f"Chat ID: {message.chat.id}\nДобавьте этот номер в админке трекера → Опросы в Telegram → Добавить чат."
    )
