"""Telegram-бот трекера: отвечает на /start и открывает мини-апп.

Запуск: python -m app.bot (отдельный контейнер в docker-compose).
Уведомления о задачах шлёт не этот процесс, а сам бэкенд через Bot API
(services/telegram_service.py) — бот нужен только для общения в чате.
"""
import logging
import threading
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories import user_repository
from app.services.telegram_service import call, webapp_button

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ik-bot")

WELCOME_NEW = (
    "Это трекер задач «Информационного комитета».\n\n"
    "Нажмите «Открыть трекер» и один раз войдите по логину и паролю. "
    "Дальше трекер будет открываться сразу, а уведомления о задачах будут приходить сюда."
)
WELCOME_LINKED = (
    "{name}, трекер на месте: нажмите «Открыть трекер» или кнопку меню слева от поля ввода. "
    "Уведомления о задачах приходят в этот чат."
)
HELP = (
    "Трекер открывается кнопкой «Открыть трекер» или кнопкой меню слева от поля ввода. "
    "Тот же трекер есть в браузере: {url}"
)


def _setup() -> None:
    # Кнопка меню у поля ввода открывает мини-апп в любом чате с ботом.
    call(
        "setChatMenuButton",
        {"menu_button": {"type": "web_app", "text": "Трекер", "web_app": {"url": settings.webapp_url}}},
    )
    call(
        "setMyCommands",
        {"commands": [
            {"command": "start", "description": "Открыть трекер"},
            {"command": "help", "description": "Как пользоваться"},
        ]},
    )


def _reply(chat_id: int, text: str) -> None:
    call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": [[webapp_button("Открыть трекер")]]},
        },
    )


def _handle(update: dict) -> None:
    message = update.get("message")
    if not message or message.get("chat", {}).get("type") != "private":
        return
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text.startswith("/help"):
        _reply(chat_id, HELP.format(url=settings.webapp_url))
        return

    db = SessionLocal()
    try:
        user = user_repository.get_by_telegram_id(db, message["from"]["id"])
        name = user.full_name.split()[0] if user else None
    finally:
        db.close()
    _reply(chat_id, WELCOME_LINKED.format(name=name) if name else WELCOME_NEW)


def main() -> None:
    if not settings.telegram_bot_token:
        # Без токена не падаем в цикл перезапусков — просто ждём, пока его зададут.
        logger.warning("TELEGRAM_BOT_TOKEN не задан — бот не запущен")
        threading.Event().wait()

    while True:
        try:
            _setup()
            break
        except Exception as exc:
            logger.warning("Не удалось настроить бота: %s — повтор через 10 с", exc)
            time.sleep(10)
    logger.info("Бот запущен, мини-апп: %s", settings.webapp_url)

    offset = 0
    while True:
        try:
            updates = call(
                "getUpdates",
                {"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                timeout=40,
            )
        except Exception as exc:
            logger.warning("getUpdates: %s — повтор через 5 с", exc)
            time.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                _handle(update)
            except Exception:
                logger.exception("Ошибка обработки сообщения")


if __name__ == "__main__":
    main()
