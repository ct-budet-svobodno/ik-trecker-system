import datetime
import enum

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.direction import Direction
from app.models.user import LeadershipPosition, User


class LeadershipTaskStatus(str, enum.Enum):
    TODO = "todo"
    DONE = "done"  # «выполнено»


class LeadershipTask(Base):
    """Запись из «Таймлайна руководства» — отдельная сущность, не обычная задача.

    Привязана ко дню и ровно к одной «строке» сетки: направлению (direction_id),
    должности тройки (position) или Редакции (is_editorial — общая строка
    руководителей СМИ и Дизайна). Видимость выводится из этой привязки,
    отдельного assignee нет.

    Запись четвёрки (position) может быть «блоком» — накрывать прямоугольник:
    несколько дней (date … end_date включительно) и несколько соседних
    должностей (position … position_end по порядку строк) и иметь свой цвет.
    Для одиночной клетки end_date/position_end пусты (= date/position).
    """

    __tablename__ = "leadership_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # Конец блока по дням (вкл.); None — блок в один день.
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[LeadershipTaskStatus] = mapped_column(
        Enum(LeadershipTaskStatus), nullable=False, default=LeadershipTaskStatus.TODO
    )

    # Ровно одно из трёх задаёт строку сетки.
    direction_id: Mapped[int | None] = mapped_column(ForeignKey("directions.id"), nullable=True)
    position: Mapped[LeadershipPosition | None] = mapped_column(
        Enum(LeadershipPosition), nullable=True
    )
    # Нижняя должность блока четвёрки (вкл.); None — блок в одну строку.
    position_end: Mapped[LeadershipPosition | None] = mapped_column(
        Enum(LeadershipPosition), nullable=True
    )
    is_editorial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Цвет блока четвёрки (hex, напр. «#e0533d»); None — цвет по умолчанию.
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    direction: Mapped[Direction | None] = relationship(foreign_keys=[direction_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
