import datetime
import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class ZavodNodeStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


zavod_node_assignees = Table(
    "zavod_node_assignees",
    Base.metadata,
    Column("node_id", ForeignKey("zavod_nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class ZavodBoard(Base):
    """Доска ZAVOD — бесконечный холст с карточками тем и связями между ними."""

    __tablename__ = "zavod_boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])


class ZavodNode(Base):
    """Карточка на холсте.

    Координаты x/y и размеры — в «мировых» единицах холста, а не в пикселях
    экрана: зум и панорама живут только на клиенте и в БД не попадают.
    """

    __tablename__ = "zavod_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("zavod_boards.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ZavodNodeStatus] = mapped_column(
        Enum(ZavodNodeStatus), nullable=False, default=ZavodNodeStatus.TODO
    )
    # Цвет карточки (hex, напр. «#e0533d»); None — цвет по умолчанию.
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=220)
    height: Mapped[float] = mapped_column(Float, nullable=False, default=120)

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    assignees: Mapped[list[User]] = relationship(
        secondary=zavod_node_assignees,
        order_by="User.full_name",
        lazy="selectin",
    )


class ZavodEdge(Base):
    """Связь между двумя карточками. Направленная: source → target."""

    __tablename__ = "zavod_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("zavod_boards.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("zavod_nodes.id"), nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("zavod_nodes.id"), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
