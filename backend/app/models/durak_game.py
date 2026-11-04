import datetime
import enum

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class DurakGameStatus(str, enum.Enum):
    WAITING = "waiting"  # ждём второго игрока по приглашению
    READY_CHECK = "ready_check"  # второй нашёлся, оба подтверждают участие
    PLAYING = "playing"
    FINISHED = "finished"
    CANCELLED = "cancelled"  # лобби закрыто


class DurakGame(Base):
    """Партия в подкидного (раздел «Игры»). Место 0 — создатель, место 1 —
    присоединившийся по коду или бот. Сама раскладка — JSON в state
    (см. app/games/durak.py), version растёт с каждым ходом: по ней клиент
    понимает, что пора перерисовать стол, а сервер — что ход сделан по
    устаревшей картине."""

    __tablename__ = "durak_games"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    host_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guest_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    vs_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[DurakGameStatus] = mapped_column(
        Enum(DurakGameStatus), nullable=False, default=DurakGameStatus.WAITING
    )
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Проверка готовности после прихода второго. Больше не используется:
    # оба жмут «Готов» без срока. Колонка оставлена для старых партий.
    ready_deadline: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    host_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guest_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Сообщение-приглашение в чате актива: его правим по ходу партии.
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    host: Mapped[User] = relationship(foreign_keys=[host_id])
    guest: Mapped[User | None] = relationship(foreign_keys=[guest_id])
