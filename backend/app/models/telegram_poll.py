import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelegramPoll(Base):
    __tablename__ = "telegram_polls"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    chat_title: Mapped[str | None] = mapped_column(String(255))
    chat_delivery: Mapped[str | None] = mapped_column(String(16))
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


class TelegramPollRecipient(Base):
    __tablename__ = "telegram_poll_recipients"

    poll_id: Mapped[int] = mapped_column(ForeignKey("telegram_polls.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(String(128))
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    delivery: Mapped[str] = mapped_column(String(16), default="pending")
    choice: Mapped[int | None] = mapped_column()
    voted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class TelegramPollChat(Base):
    __tablename__ = "telegram_poll_chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255))
