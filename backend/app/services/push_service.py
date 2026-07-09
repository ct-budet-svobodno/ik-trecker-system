"""Отправка Web Push-уведомлений.

Отправка идёт в фоновом потоке, чтобы не тормозить HTTP-ответ. Если VAPID-ключи
не заданы (например, в тестах) — тихий no-op. Подписки, на которые push-сервис
браузера ответил 404/410, считаются мёртвыми и удаляются.
"""
import json
import logging
import threading

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories import push_subscription_repository

logger = logging.getLogger(__name__)


def push_enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def _send_batch(subs: list[dict], payload: str) -> None:
    dead_endpoints = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                dead_endpoints.append(sub["endpoint"])
            else:
                logger.warning("Web push не доставлен (%s): %s", status, exc)
        except Exception as exc:  # сеть и пр. — уведомления не критичны
            logger.warning("Web push ошибка отправки: %s", exc)

    if dead_endpoints:
        # Отдельная сессия: мы в фоновом потоке, сессия запроса уже закрыта.
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            for endpoint in dead_endpoints:
                push_subscription_repository.delete_by_endpoint(db, endpoint)
        finally:
            db.close()


def send_to_users(db: Session, user_ids: list[int], *, title: str, body: str, url: str) -> None:
    """Отправить пуш всем подпискам перечисленных пользователей (не блокируя запрос)."""
    if not push_enabled():
        return
    subs = []
    for user_id in set(user_ids):
        for sub in push_subscription_repository.list_for_user(db, user_id):
            subs.append({"endpoint": sub.endpoint, "p256dh": sub.p256dh, "auth": sub.auth})
    if not subs:
        return
    payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
    threading.Thread(target=_send_batch, args=(subs, payload), daemon=True).start()


def send_to_user(db: Session, user_id: int | None, *, title: str, body: str, url: str) -> None:
    if user_id is None:
        return
    send_to_users(db, [user_id], title=title, body=body, url=url)
