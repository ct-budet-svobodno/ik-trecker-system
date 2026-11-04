import datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.direction import Direction
from app.models.user import User


class UserProfile(Base):
    """Анкета, которую человек заполняет в мини-аппе при первом входе: без неё
    (и одобрения админа) доступа к трекеру нет. Фото лежат файлами в
    settings.profile_photos_dir, здесь — их имена."""

    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    birthday: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    direction_id: Mapped[int | None] = mapped_column(ForeignKey("directions.id", ondelete="SET NULL"), nullable=True)
    study_group: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    clothes_size: Mapped[str] = mapped_column(String(16), nullable=False)
    other_units: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    photo1: Mapped[str] = mapped_column(String(128), nullable=False)
    photo2: Mapped[str] = mapped_column(String(128), nullable=False)
    # file_id тех же фото в Telegram (из ответа на альбом в группу-архив) — по
    # ним бот показывает и пересылает фото, своих файлов у него нет.
    photo1_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    photo2_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    submitted_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship()
    direction: Mapped[Direction | None] = relationship()
