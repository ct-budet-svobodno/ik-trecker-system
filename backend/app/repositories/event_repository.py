from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event


def list_all(db: Session) -> list[Event]:
    return list(db.scalars(select(Event).order_by(Event.start_at)))


def get_by_id(db: Session, event_id: int) -> Event | None:
    return db.get(Event, event_id)


def create(
    db: Session,
    *,
    title: str,
    description: str,
    location: str | None,
    start_at: datetime,
    end_at: datetime | None,
    created_by_id: int,
) -> Event:
    event = Event(
        title=title,
        description=description,
        location=location,
        start_at=start_at,
        end_at=end_at,
        created_by_id=created_by_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_fields(db: Session, event: Event, fields: dict) -> Event:
    for key, value in fields.items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


def delete(db: Session, event: Event) -> None:
    db.delete(event)
    db.commit()
