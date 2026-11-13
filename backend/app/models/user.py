import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class RegistrationStatus(str, enum.Enum):
    """Заявка из мини-аппа: человек заполнил анкету и ждёт решения админа.
    Заведённые админом аккаунты — сразу APPROVED."""

    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


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
    # Доступ к разделу ZAVOD (доска тем). Ставит флаг админ; сверх этого раздел
    # видят админы и руководство — см. геттер isZavod на фронте.
    is_zavod: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # В активе ИК (галочка в «Пользователях»). Ставится сам, когда человек
    # заполнил анкету — в мини-аппе или в боте.
    is_activist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Направления, в которых человек состоит (может быть несколько; не путать
    # с руководством — direction_heads). Из анкеты, правит админ.
    directions: Mapped[list["Direction"]] = relationship(  # noqa: F821
        secondary="direction_members", order_by="Direction.sort_order", lazy="selectin"
    )
    # Привязанный Telegram-аккаунт: вход в мини-апп без пароля и уведомления от бота.
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Пока заявка не одобрена, is_active=False — вход и назначения закрыты.
    registration_status: Mapped[RegistrationStatus] = mapped_column(
        Enum(RegistrationStatus), nullable=False, default=RegistrationStatus.APPROVED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def direction_ids(self) -> list[int]:
        return [d.id for d in self.directions]

    @property
    def telegram_linked(self) -> bool:
        return self.telegram_id is not None
