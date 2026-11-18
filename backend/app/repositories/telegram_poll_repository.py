from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.telegram_poll import TelegramPoll, TelegramPollRecipient
from app.models.user import RegistrationStatus, User


def audience(db: Session):
    return list(db.scalars(select(User).where(
        User.is_active.is_(True), User.registration_status == RegistrationStatus.APPROVED,
    ).order_by(User.full_name, User.id)))


def recipients(db: Session, poll_id: int):
    return list(db.scalars(select(TelegramPollRecipient).where(
        TelegramPollRecipient.poll_id == poll_id,
    ).order_by(TelegramPollRecipient.full_name, TelegramPollRecipient.user_id)))


def list_all(db: Session):
    return list(db.scalars(select(TelegramPoll).order_by(TelegramPoll.id.desc())))


def create(db: Session, admin_id: int, text: str, options: list[str], users: list[User], *, chat=None):
    poll = TelegramPoll(author_id=admin_id, text=text, options=options,
        chat_id=chat.id if chat else None, chat_title=chat.title if chat else None,
        chat_delivery="pending" if chat else None)
    db.add(poll)
    db.flush()
    db.add_all([TelegramPollRecipient(
        poll_id=poll.id, user_id=u.id, telegram_id=u.telegram_id,
        full_name=u.full_name, telegram_username=u.telegram_username,
        delivery="pending" if u.telegram_id else "no_telegram",
    ) for u in users])
    db.commit()
    return poll
