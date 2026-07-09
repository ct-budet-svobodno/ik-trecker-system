from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.direction import Direction, direction_heads
from app.models.user import User


def list_all(db: Session) -> list[Direction]:
    return list(db.scalars(select(Direction).order_by(Direction.sort_order, Direction.id)))


def get_by_id(db: Session, direction_id: int) -> Direction | None:
    return db.get(Direction, direction_id)


def get_id_by_short_code(db: Session, short_code: str) -> int | None:
    return db.scalar(
        select(Direction.id).where(Direction.short_code == short_code)
    )


def list_ids_headed_by(db: Session, user_id: int) -> set[int]:
    """id направлений, где пользователь — руководитель (head)."""
    rows = db.scalars(
        select(direction_heads.c.direction_id).where(direction_heads.c.user_id == user_id)
    )
    return set(rows)


def set_heads(db: Session, direction: Direction, heads: list[User]) -> Direction:
    direction.heads = heads
    db.commit()
    db.refresh(direction)
    return direction
