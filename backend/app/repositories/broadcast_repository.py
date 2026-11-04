from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.broadcast import Broadcast, BroadcastStatus


def get(db: Session, broadcast_id: int) -> Broadcast | None:
    return db.get(Broadcast, broadcast_id)


def list_recent(db: Session, limit: int = 20) -> list[Broadcast]:
    query = (
        select(Broadcast)
        .options(joinedload(Broadcast.author))
        .order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def sending(db: Session) -> Broadcast | None:
    return db.scalar(select(Broadcast).where(Broadcast.status == BroadcastStatus.SENDING))


def create(db: Session, *, author_id: int, text: str, buttons: list[dict], total: int) -> Broadcast:
    broadcast = Broadcast(author_id=author_id, text=text, buttons=buttons, total=total)
    db.add(broadcast)
    db.commit()
    db.refresh(broadcast)
    return broadcast


def save(db: Session, broadcast: Broadcast, **fields) -> Broadcast:
    for key, value in fields.items():
        setattr(broadcast, key, value)
    db.commit()
    return broadcast
