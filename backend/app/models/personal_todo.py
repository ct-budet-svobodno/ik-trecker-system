import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PersonalTodo(Base):
    """Пункт личного списка «Мой день». Виден и доступен только владельцу —
    в общую доску, таймлайн и чужие выборки не попадает."""

    __tablename__ = "personal_todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
