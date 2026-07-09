import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class LeadershipPosition(str, enum.Enum):
    """Должности руководства. У пользователя не более одной должности."""

    CHAIRMAN = "chairman"  # Председатель
    SECRETARY = "secretary"  # Секретарь
    FIRST_DEPUTY = "first_deputy"  # Первый заместитель
    BRAND_MANAGER = "brand_manager"  # Бренд-менеджер


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    leadership_position: Mapped[LeadershipPosition | None] = mapped_column(
        Enum(LeadershipPosition), nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Участник Редакции (СМИ + Дизайн) — видит SMM-календарь и может ставиться
    # райтером/дизайнером. Ставит флаг админ.
    is_editorial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
