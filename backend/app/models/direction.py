from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

direction_heads = Table(
    "direction_heads",
    Base.metadata,
    Column("direction_id", ForeignKey("directions.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

# Где человек состоит (их может быть несколько) — не путать с руководством выше.
direction_members = Table(
    "direction_members",
    Base.metadata,
    Column("direction_id", ForeignKey("directions.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Direction(Base):
    __tablename__ = "directions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    heads: Mapped[list["User"]] = relationship(  # noqa: F821
        secondary=direction_heads,
        order_by="User.full_name",
        lazy="selectin",
    )
