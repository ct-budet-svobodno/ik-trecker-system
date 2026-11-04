import datetime
import enum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class SurveyStatus(str, enum.Enum):
    DRAFT = "draft"  # собирается, никому не отправлена
    OPEN = "open"  # отправлена, ответы принимаются
    CLOSED = "closed"  # ответы больше не принимаются


class Survey(Base):
    """Анкета-опрос: админ собирает вопросы и отправляет выбранным людям
    (раздел «Анкеты»). questions — [{id, type, title, hint, required, options, max}],
    см. schemas/survey.py."""

    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[SurveyStatus] = mapped_column(
        Enum(SurveyStatus), nullable=False, default=SurveyStatus.DRAFT
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Последнее напоминание тем, кто не ответил, — не чаще раза в 30 мин.
    reminded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped[User | None] = relationship()


class SurveyRecipient(Base):
    """Кому анкета отправлена (видит её у себя и может ответить)."""

    __tablename__ = "survey_recipients"

    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    sent_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship()


class SurveyResponse(Base):
    """Ответ человека: answers — {id вопроса: значение}. Пока анкета открыта,
    его можно переотправить — хранится последняя версия."""

    __tablename__ = "survey_responses"
    __table_args__ = (UniqueConstraint("survey_id", "user_id", name="uq_survey_responses_survey_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    submitted_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
