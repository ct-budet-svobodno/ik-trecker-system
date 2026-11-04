import datetime
import enum

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class BunkerStatus(str, enum.Enum):
    WAITING = "waiting"  # лобби: собираем игроков по приглашению
    PLAYING = "playing"
    FINISHED = "finished"
    CANCELLED = "cancelled"  # создатель распустил лобби или остановил партию


class BunkerGame(Base):
    """Партия в «Бункер» (раздел «Игры»). Игроков от 4 до 16 — они в bunker_players,
    место = порядок входа; карты и ход партии — JSON в state (см. app/games/bunker.py),
    version растёт с каждым действием.

    Стол (title задан) заводит админ для очной игры: состав задаётся списком,
    по ссылке не войти; ведущий (host) может сам не играть — тогда он наблюдатель."""

    __tablename__ = "bunker_games"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    host_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[BunkerStatus] = mapped_column(
        Enum(BunkerStatus), nullable=False, default=BunkerStatus.WAITING
    )
    # Пусто, пока партия не началась.
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Начало текущей фазы (UTC без tz) — по нему фронт ведёт таймер обсуждения.
    phase_started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
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
    players: Mapped[list["BunkerPlayer"]] = relationship(
        back_populates="game", order_by="BunkerPlayer.seat", cascade="all, delete-orphan"
    )

    @property
    def is_table(self) -> bool:
        return self.title is not None


class BunkerPlayer(Base):
    __tablename__ = "bunker_players"
    __table_args__ = (UniqueConstraint("game_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("bunker_games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seat: Mapped[int] = mapped_column(Integer, nullable=False)

    game: Mapped[BunkerGame] = relationship(back_populates="players")
    user: Mapped[User] = relationship()
