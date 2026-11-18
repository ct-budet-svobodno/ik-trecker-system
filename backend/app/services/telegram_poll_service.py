"""Опросы в личных сообщениях: один изменяемый голос на получателя."""
import datetime
import logging
import time

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.telegram_poll import TelegramPoll, TelegramPollRecipient, TelegramPollChat
from app.models.user import RegistrationStatus, User
from app.repositories import telegram_poll_repository as repo
from app.services import broadcast_service, telegram_service

logger = logging.getLogger(__name__)


def view(db: Session, poll: TelegramPoll, detail=False):
    rows = repo.recipients(db, poll.id)
    result = dict(chat_id=poll.chat_id, chat_title=poll.chat_title, chat_delivery=poll.chat_delivery, id=poll.id, text=poll.text, options=poll.options, closed=poll.closed,
                  created_at=poll.created_at, total=len(rows),
                  voted=sum(r.choice is not None for r in rows),
                  counts=[sum(r.choice == i for r in rows) for i in range(len(poll.options))],
                  sent=sum(r.delivery == "sent" for r in rows),
                  pending=sum(r.delivery in ("pending", "sending") for r in rows),
                  failed=sum(r.delivery in ("failed", "no_telegram") for r in rows))
    if detail:
        result["recipients"] = [dict(user_id=r.user_id, full_name=r.full_name,
            telegram_username=r.telegram_username, delivery=r.delivery,
            choice=r.choice, voted_at=r.voted_at) for r in rows]
    return result


def create(db: Session, admin: User, data):
    if not telegram_service.telegram_enabled():
        raise ValueError("Бот не подключён")
    available = {u.id: u for u in repo.audience(db)}
    ids = set(data.user_ids)
    if not ids.issubset(available):
        raise ValueError("В списке есть неактивные или неодобренные участники. Обновите страницу")
    users = [available[i] for i in sorted(ids)]
    if not any(u.telegram_id for u in users):
        raise ValueError("У выбранных участников не подключён Telegram")
    chat = db.get(TelegramPollChat, data.chat_id) if data.chat_id is not None else None
    if data.chat_id is not None and chat is None:
        raise ValueError("Сначала добавьте чат в список доступных")
    if chat is not None:
        validate_chat(chat.id)
    poll = repo.create(db, admin.id, data.text, data.options, users, chat=chat)
    broadcast_service._spawn(deliver, poll.id)
    return poll


def deliver(poll_id: int):
    with SessionLocal() as db:
        poll = db.get(TelegramPoll, poll_id)
        if poll.chat_id is not None:
            deliver_group(db, poll)
            return
        for recipient in repo.recipients(db, poll_id):
            if recipient.delivery != "pending":
                continue
            # Сохраняем попытку до Telegram: неизвестный результат после сбоя
            # не должен приводить к повторной отправке.
            claimed = db.execute(update(TelegramPollRecipient).where(
                TelegramPollRecipient.poll_id == poll_id,
                TelegramPollRecipient.user_id == recipient.user_id,
                TelegramPollRecipient.delivery == "pending",
            ).values(delivery="sending")).rowcount
            db.commit()
            if not claimed:
                continue
            payload = dict(chat_id=recipient.telegram_id,
                text=broadcast_service.render_text(poll.text) +
                     "\n\n<i>Выберите один вариант. Ответ виден администратору; выбор можно изменить.</i>",
                parse_mode="HTML", reply_markup={"inline_keyboard": [
                    [{"text": label, "callback_data": f"ikpoll:{poll_id}:{i}"}]
                    for i, label in enumerate(poll.options)
                ]})
            try:
                sent = broadcast_service._send(payload)
            except Exception:
                logger.exception("Не удалось отправить опрос %s", poll_id)
                sent = False
            recipient.delivery = "sent" if sent else "failed"
            db.commit()
            time.sleep(broadcast_service.SEND_INTERVAL)


def vote(db: Session, data):
    # Транзакционная запись: закрытие опроса и голосование не обходят друг друга.
    stmt = update(TelegramPollRecipient).where(
        TelegramPollRecipient.poll_id == data.poll_id,
        TelegramPollRecipient.telegram_id == data.telegram_id,
        TelegramPollRecipient.poll_id.in_(select(TelegramPoll.id).where(TelegramPoll.closed.is_(False))),
        TelegramPollRecipient.user_id.in_(select(User.id).where(
            User.telegram_id == data.telegram_id, User.is_active.is_(True),
            User.registration_status == RegistrationStatus.APPROVED,
        )),
    ).values(choice=data.choice, voted_at=datetime.datetime.now(datetime.UTC))
    poll = db.get(TelegramPoll, data.poll_id)
    if poll is None or data.choice >= len(poll.options):
        raise ValueError("Опрос или вариант ответа не найден")
    if poll.chat_id is not None:
        if data.chat_id != poll.chat_id:
            raise ValueError("Голосовать нужно в чате, куда отправлен опрос")
    elif data.chat_id is not None and data.chat_id != data.telegram_id:
        raise ValueError("Голосовать нужно в личном сообщении бота")
    changed = db.execute(stmt).rowcount
    if not changed:
        db.rollback()
        raise ValueError("Опрос закрыт или вы не входите в список получателей")
    db.commit()
    return poll.options[data.choice]


def recover_delivery():
    """Продолжить очередь при старте; незавершённые попытки не дублируем."""
    if not telegram_service.telegram_enabled():
        return
    with SessionLocal() as db:
        db.execute(update(TelegramPollRecipient).where(
            TelegramPollRecipient.delivery == "sending",
        ).values(delivery="failed"))
        db.execute(update(TelegramPoll).where(TelegramPoll.chat_delivery == "sending").values(chat_delivery="failed"))
        db.commit()
        ids = list(db.scalars(select(TelegramPollRecipient.poll_id).where(
            TelegramPollRecipient.delivery == "pending",
        ).distinct()))
    for poll_id in ids:
        deliver(poll_id)


def validate_chat(chat_id: int) -> dict:
    try:
        chat = telegram_service.call("getChat", {"chat_id": chat_id})
        if chat.get("type") not in ("group", "supergroup"):
            raise ValueError("Выберите группу или супергруппу Telegram")
        me = telegram_service.call("getMe", {})
        member = telegram_service.call("getChatMember", {"chat_id": chat_id, "user_id": me["id"]})
        status = member.get("status")
        permissions = chat.get("permissions", {})
        if status in ("left", "kicked") or (status == "restricted" and
                (not member.get("is_member") or not member.get("can_send_messages"))) or (
                status == "member" and permissions.get("can_send_messages") is False):
            raise ValueError("У бота нет права отправлять сообщения в этот чат")
        return chat
    except ValueError:
        raise
    except Exception:
        raise ValueError("Не удалось проверить чат. Проверьте Chat ID и добавьте в него бота") from None


def add_chat(db: Session, chat_id: int):
    if not telegram_service.telegram_enabled():
        raise ValueError("Бот не подключён")
    info = validate_chat(chat_id)
    chat = db.get(TelegramPollChat, chat_id)
    if chat is None:
        chat = TelegramPollChat(id=chat_id, title=info.get("title", str(chat_id)))
        db.add(chat)
    else:
        chat.title = info.get("title", str(chat_id))
    db.commit()
    return {"id": chat.id, "title": chat.title}


def deliver_group(db: Session, poll: TelegramPoll):
    claimed = db.execute(update(TelegramPoll).where(
        TelegramPoll.id == poll.id, TelegramPoll.chat_delivery == "pending",
    ).values(chat_delivery="sending")).rowcount
    db.commit()
    if not claimed:
        # После сбоя результат отправки неизвестен; повторное сообщение не шлём.
        if poll.chat_delivery == "failed":
            db.execute(update(TelegramPollRecipient).where(
                TelegramPollRecipient.poll_id == poll.id,
                TelegramPollRecipient.delivery.in_(["pending", "sending"]),
            ).values(delivery="failed"))
            db.commit()
        return
    payload = dict(chat_id=poll.chat_id, text=broadcast_service.render_text(poll.text) +
        "\n\n<i>Один вариант на участника. Ответы видны администратору; выбор можно изменить до закрытия опроса.</i>",
        parse_mode="HTML", reply_markup={"inline_keyboard": [
            [{"text": label, "callback_data": f"ikpoll:{poll.id}:{i}"}]
            for i, label in enumerate(poll.options)
        ]})
    sent = broadcast_service._send(payload)
    poll.chat_delivery = "sent" if sent else "failed"
    db.execute(update(TelegramPollRecipient).where(
        TelegramPollRecipient.poll_id == poll.id,
        TelegramPollRecipient.telegram_id.is_not(None),
    ).values(delivery="sent" if sent else "failed"))
    db.commit()
