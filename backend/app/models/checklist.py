import datetime
import enum

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChecklistStatus(str, enum.Enum):
    DRAFT = "draft"  # подготовлен, ещё не отправлен
    SENT = "sent"
    FAILED = "failed"  # Telegram не принял: человек не запускал бота


class ChecklistCard(Base):
    """Чек-лист «Найди того, кто…» одного человека: три факта и картинка.

    Картинку рисует админка (canvas) и загружает сюда, рассылает бэкенд от бота.
    Фото в ответ принимает бот flood — для этого при отправке строка
    дублируется в его базу (таблица checklists, см. checklist_service)."""

    __tablename__ = "checklist_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    facts: Mapped[list] = mapped_column(JSON, nullable=False)
    image_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ChecklistStatus] = mapped_column(
        Enum(ChecklistStatus), nullable=False, default=ChecklistStatus.DRAFT
    )
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
