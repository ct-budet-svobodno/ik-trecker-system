from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WelcomeBookProgress(Base):
    __tablename__ = "welcome_book_progress"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    max_page: Mapped[int] = mapped_column(Integer, nullable=False)
    first_opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
