"""Сообщения от бота: уведомления о задачах приходят в Telegram.

Как и push_service: отправка в фоновом потоке, ошибки не роняют запрос,
без токена бота — тихий no-op.
"""
import json
import logging
import threading
import urllib.error
import urllib.request
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories import user_repository

logger = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


def telegram_enabled() -> bool:
    return bool(settings.telegram_bot_token)


def call(method: str, payload: dict, timeout: float = 10) -> dict:
    """Синхронный вызов Bot API. Кидает исключение при сетевой ошибке или ok=false."""
    request = urllib.request.Request(
        API.format(token=settings.telegram_bot_token, method=method),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read())
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram вернул ошибку"))
    return body["result"]


_me: dict | None = None


def _get_me() -> dict:
    """Профиль бота (getMe). Запрашиваем у Telegram один раз и запоминаем."""
    global _me
    if _me is None and telegram_enabled():
        try:
            _me = call("getMe", {}, timeout=5)
        except Exception as exc:
            logger.warning("Telegram getMe: %s", exc)
    return _me or {}


def bot_username() -> str | None:
    """Имя бота (для ссылки t.me/...)."""
    return _get_me().get("username")


def startapp_url(param: str) -> str | None:
    """Ссылка, открывающая трекер с параметром запуска (start_param).

    Если у бота в BotFather настроен основной мини-апп — t.me/<бот>?startapp=…
    открывает его сразу, из любого чата. Иначе — t.me/<бот>?start=…: человек
    попадает в личку, и бот (flood, /start durak_…) даёт кнопку мини-аппа.
    """
    me = _get_me()
    username = me.get("username")
    if not username:
        return None
    key = "startapp" if me.get("has_main_web_app") else "start"
    return f"https://t.me/{username}?{key}={param}"


def webapp_button(text: str, path: str = "/") -> dict:
    """Кнопка, открывающая трекер мини-аппом на нужной странице."""
    return {"text": text, "web_app": {"url": settings.webapp_url.rstrip("/") + path}}


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _send_batch(messages: list[dict]) -> None:
    for message in messages:
        try:
            call("sendMessage", message)
        except urllib.error.HTTPError as exc:
            # 403 — пользователь остановил бота; не страшно, просто пропускаем.
            logger.info("Telegram не доставил сообщение (%s)", exc.code)
        except Exception as exc:  # сеть и пр. — уведомления не критичны
            logger.warning("Telegram ошибка отправки: %s", exc)


def send_to_users(db: Session, user_ids: list[int], *, title: str, body: str, url: str) -> None:
    if not telegram_enabled():
        return
    messages = []
    for user_id in set(user_ids):
        user = user_repository.get_by_id(db, user_id)
        if user is None or user.telegram_id is None or not user.is_active:
            continue
        messages.append(
            {
                "chat_id": user.telegram_id,
                "text": f"<b>{_escape(title)}</b>\n{_escape(body)}",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": [[webapp_button("Открыть", url)]]},
            }
        )
    if messages:
        threading.Thread(target=_send_batch, args=(messages,), daemon=True).start()


# --- Сообщения в групповом чате (приглашения в игры) ---

def send_photo(chat_id: int, photo_url: str, caption: str, buttons: list[dict] | None) -> int | None:
    """Синхронно отправить фото с подписью; вернуть message_id (None — не вышло).
    Синхронно — потому что id нужен сразу: по нему сообщение потом правим."""
    if not telegram_enabled():
        return None
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [buttons]}
    try:
        return call("sendPhoto", payload)["message_id"]
    except Exception as exc:
        logger.warning("Telegram sendPhoto в %s: %s", chat_id, exc)
        return None


def _edit_caption(payload: dict) -> None:
    try:
        call("editMessageCaption", payload)
    except Exception as exc:  # «message is not modified», удалённое сообщение — не критично
        logger.info("Telegram editMessageCaption: %s", exc)


def edit_caption(chat_id: int, message_id: int, caption: str, buttons: list[dict] | None) -> None:
    """Поправить подпись и кнопки (пустой buttons — убрать кнопки). В фоне."""
    if not telegram_enabled():
        return
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [buttons] if buttons else []},
    }
    threading.Thread(target=_edit_caption, args=(payload,), daemon=True).start()


def escape(text: str) -> str:
    return _escape(text)


# --- Анкеты новых участников ---

def _post_multipart(method: str, fields: dict[str, str], files: dict[str, tuple[str, bytes]]):
    """Bot API с вложениями (multipart/form-data) — для фото, которых нет по ссылке."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    for name, (filename, data) in files.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n".encode() + data + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        API.format(token=settings.telegram_bot_token, method=method),
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read())
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram вернул ошибку"))
    return body["result"]


def send_photo_file(chat_id: int, data: bytes, caption: str, filename: str = "photo.jpg") -> dict:
    """Синхронно отправить картинку файлом (её нет по ссылке). Кидает исключение."""
    return _post_multipart(
        "sendPhoto", {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"}, {"photo": (filename, data)}
    )


def download_file(file_id: str) -> bytes:
    """Скачать файл, присланный боту (фото и т.п.), по его file_id."""
    path = call("getFile", {"file_id": file_id})["file_path"]
    url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{path}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def _send_album(chat_id: int, photos: list[bytes], caption: str, on_sent=None) -> None:
    media = [
        {"type": "photo", "media": f"attach://photo{i}", **({"caption": caption, "parse_mode": "HTML"} if i == 0 else {})}
        for i in range(len(photos))
    ]
    try:
        messages = _post_multipart(
            "sendMediaGroup",
            {"chat_id": str(chat_id), "media": json.dumps(media, ensure_ascii=False)},
            {f"photo{i}": (f"photo{i}.jpg", data) for i, data in enumerate(photos)},
        )
    except Exception as exc:
        logger.warning("Telegram: анкета не ушла в архив %s: %s", chat_id, exc)
        return
    if on_sent is not None:
        # Самый крупный размер каждого фото — его file_id потом годится для бота.
        file_ids = [m["photo"][-1]["file_id"] for m in messages if m.get("photo")]
        try:
            on_sent(file_ids)
        except Exception as exc:
            logger.warning("Telegram: не сохранили file_id фото анкеты: %s", exc)


def send_album(chat_id: int, photos: list[bytes], caption: str, on_sent=None) -> None:
    """Альбом из фото с подписью у первого (подпись до 1024 символов). В фоне;
    on_sent(file_ids) — после отправки, с id фото в Telegram."""
    if not telegram_enabled():
        return
    threading.Thread(
        target=_send_album, args=(chat_id, photos, caption[:1024], on_sent), daemon=True
    ).start()


def send_message(chat_id: int, text: str, buttons: list[dict] | None = None) -> None:
    """Сообщение конкретному чату (например, человеку без активного аккаунта). В фоне."""
    if not telegram_enabled():
        return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [buttons]}
    threading.Thread(target=_send_batch, args=([payload],), daemon=True).start()
