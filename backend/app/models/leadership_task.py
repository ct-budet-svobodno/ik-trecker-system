import datetime
import enum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.direction import Direction
from app.models.user import LeadershipPosition, User


class LeadershipTaskStatus(str, enum.Enum):
    TODO = "todo"
    DONE = "done"  # «выполнено»


class LeadershipTask(Base):
    """Запись из «Таймлайна руководства» — отдельная сущность, не обычная задача.

    Привязана ко дню и ровно к одной «строке» сетки: либо к направлению
    (direction_id), либо к должности тройки (position). Видимость выводится из
    этой привязки (direction_heads / держатель должности), отдельного assignee нет.
    """

    __tablename__ = "leadership_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[LeadershipTaskStatus] = mapped_column(
        Enum(LeadershipTaskStatus), nullable=False, default=LeadershipTaskStatus.TODO
    )

    # Ровно одно из двух задаёт строку сетки.
    direction_id: Mapped[int | None] = mapped_column(ForeignKey("directions.id"), nullable=True)
    position: Mapped[LeadershipPosition | None] = mapped_column(
        Enum(LeadershipPosition), nullable=True
    )

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    direction: Mapped[Direction | None] = relationship(foreign_keys=[direction_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
