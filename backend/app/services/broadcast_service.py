"""Рассылка от бота в личку: админ пишет текст и кнопки, бот шлёт всем, кого знает.

Получатели — Telegram id из трекера (привязанные аккаунты) и из базы бота
(анкета в личке, писавшие в чатах — bot_sync_service.known_telegram_ids).
Писать в личку бот может только тем, кто хоть раз его запускал: остальным
Telegram ответит 403 — такие считаются «не дошло».

Отправка — в фоновом потоке, ~20 сообщений в секунду (лимит Telegram — 30);
прогресс пишется в broadcasts, фронт его опрашивает. Одновременно идёт
только одна рассылка.

Разметка текста: **жирный**, __курсив__; ссылки Telegram подсвечивает сам.
Кнопка — ссылка (url) или страница трекера, открытая мини-аппом (path).
"""
import datetime
import json
import logging
import re
import threading
import time
import urllib.error

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.broadcast import Broadcast, BroadcastStatus
from app.models.user import User
from app.repositories import broadcast_repository
from app.services import bot_sync_service, telegram_service
from app.services.exceptions import BroadcastError

logger = logging.getLogger(__name__)

SEND_INTERVAL = 0.05
# Прогресс в базу — не после каждого сообщения, а пачками.
PROGRESS_EVERY = 10
# Рассылка, которая «идёт» дольше, оборвалась (перезапуск сервера) — не держим ею очередь.
STALE_AFTER = datetime.timedelta(minutes=20)


def recipients(db: Session) -> list[int]:
    tracker = db.scalars(
        select(User.telegram_id).where(User.telegram_id.is_not(None), User.is_active.is_(True))
    )
    return sorted(set(tracker) | bot_sync_service.known_telegram_ids())


def render_text(text: str) -> str:
    html = telegram_service.escape(text.strip())
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html, flags=re.S)
    return re.sub(r"__(.+?)__", r"<i>\1</i>", html, flags=re.S)


def render_buttons(buttons: list[dict]) -> list[list[dict]]:
    """Каждая кнопка — своей строкой: на телефоне так читаются длинные подписи."""
    rows = []
    for button in buttons:
        if button.get("path"):
            rows.append([telegram_service.webapp_button(button["text"], button["path"])])
        else:
            rows.append([{"text": button["text"], "url": button["url"]}])
    return rows


def _payload(chat_id: int, text: str, buttons: list[dict]) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": render_text(text),
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": render_buttons(buttons)}
    return payload


def _send(payload: dict) -> bool:
    """Одно сообщение; при 429 ждём, сколько просит Telegram, и пробуем ещё раз."""
    for _ in range(2):
        try:
            telegram_service.call("sendMessage", payload)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                return False  # 403 — не запускал бота или заблокировал, 400 — нет такого чата
            try:
                retry = json.loads(exc.read()).get("parameters", {}).get("retry_after", 1)
            except Exception:
                retry = 1
            time.sleep(min(float(retry), 30))
        except Exception as exc:
            logger.warning("Рассылка: %s", exc)
            return False
    return False


def _check_ready() -> None:
    if not telegram_service.telegram_enabled():
        raise BroadcastError("Бот не подключён — рассылка недоступна")


def send_test(admin: User, text: str, buttons: list[dict]) -> None:
    """Пробная отправка себе — синхронно, чтобы сразу сказать, если не вышло."""
    _check_ready()
    if admin.telegram_id is None:
        raise BroadcastError("К вашему аккаунту не привязан Telegram — подключите его, чтобы проверить")
    try:
        telegram_service.call("sendMessage", _payload(admin.telegram_id, text, buttons))
    except urllib.error.HTTPError as exc:
        raise BroadcastError(
            "Telegram не принял сообщение. Откройте бота и нажмите «Старт»" if exc.code == 403
            else "Telegram не принял сообщение — проверьте кнопки и ссылки"
        ) from exc
    except Exception as exc:
        raise BroadcastError("Не удалось отправить — проверьте кнопки и ссылки") from exc


def start(db: Session, admin: User, text: str, buttons: list[dict]) -> Broadcast:
    _check_ready()
    current = broadcast_repository.sending(db)
    if current is not None and _is_stale(current):
        broadcast_repository.save(db, current, status=BroadcastStatus.DONE)
        current = None
    if current is not None:
        raise BroadcastError("Уже идёт рассылка — дождитесь, пока она закончится")
    chat_ids = recipients(db)
    if not chat_ids:
        raise BroadcastError("Некому отправлять: бот пока никого не знает")
    broadcast = broadcast_repository.create(
        db, author_id=admin.id, text=text.strip(), buttons=buttons, total=len(chat_ids)
    )
    _spawn(_run, broadcast.id, chat_ids, text, buttons)
    return broadcast


def _is_stale(broadcast: Broadcast) -> bool:
    created = broadcast.created_at
    if created is None:
        return False
    if created.tzinfo is None:  # SQLite отдаёт без зоны, хранит UTC
        created = created.replace(tzinfo=datetime.UTC)
    return datetime.datetime.now(datetime.UTC) - created > STALE_AFTER


def _spawn(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def _run(broadcast_id: int, chat_ids: list[int], text: str, buttons: list[dict]) -> None:
    db = SessionLocal()
    try:
        broadcast = broadcast_repository.get(db, broadcast_id)
        sent = failed = 0
        for i, chat_id in enumerate(chat_ids, 1):
            if _send(_payload(chat_id, text, buttons)):
                sent += 1
            else:
                failed += 1
            if i % PROGRESS_EVERY == 0:
                broadcast_repository.save(db, broadcast, sent=sent, failed=failed)
            time.sleep(SEND_INTERVAL)
        broadcast_repository.save(
            db, broadcast, sent=sent, failed=failed, status=BroadcastStatus.DONE,
            finished_at=datetime.datetime.now(datetime.UTC),
        )
    except Exception:
        logger.exception("Рассылка %s оборвалась", broadcast_id)
        broadcast = broadcast_repository.get(db, broadcast_id)
        if broadcast is not None:
            broadcast_repository.save(db, broadcast, status=BroadcastStatus.DONE)
    finally:
        db.close()


def list_recent(db: Session) -> list[Broadcast]:
    return broadcast_repository.list_recent(db)


def get(db: Session, broadcast_id: int) -> Broadcast | None:
    return broadcast_repository.get(db, broadcast_id)
