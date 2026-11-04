import datetime
import enum

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class SeaBattleStatus(str, enum.Enum):
    WAITING = "waiting"  # ждём второго игрока по приглашению
    READY_CHECK = "ready_check"  # второй нашёлся, оба подтверждают участие
    PLACING = "placing"  # расставляют флот
    PLAYING = "playing"
    FINISHED = "finished"
    CANCELLED = "cancelled"  # лобби закрыто или участие не подтвердили


class SeaBattleGame(Base):
    """Партия в морской бой (раздел «Игры»). Устроена как DurakGame: место 0 —
    создатель, место 1 — присоединившийся или бот; доски — JSON в state
    (см. app/games/seabattle.py), version растёт с каждым ходом."""

    __tablename__ = "sea_battle_games"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    host_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guest_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    vs_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[SeaBattleStatus] = mapped_column(
        Enum(SeaBattleStatus), nullable=False, default=SeaBattleStatus.WAITING
    )
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Проверка готовности — как в дураке (UTC без tz), см. sea_battle_service._expire.
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
