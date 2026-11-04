import datetime
import enum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class BroadcastStatus(str, enum.Enum):
    SENDING = "sending"
    DONE = "done"


class Broadcast(Base):
    """Рассылка от бота в личку всем, кого он знает (раздел «Рассылка», только админ).
    buttons — [{text, url} | {text, path}]: ссылка или страница трекера в мини-аппе."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    buttons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[BroadcastStatus] = mapped_column(
        Enum(BroadcastStatus), nullable=False, default=BroadcastStatus.SENDING
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped[User | None] = relationship()
