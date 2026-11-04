from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class EventRsvp(Base):
    """Ответ на мероприятие: придёт человек или нет. Нет строки — не ответил."""

    __tablename__ = "event_rsvps"

    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    going: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship()
