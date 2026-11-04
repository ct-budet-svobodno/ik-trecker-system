from datetime import datetime

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.orm import Session, joinedload

from app.models.event import Event
from app.models.event_rsvp import EventRsvp


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
    # PRAGMA foreign_keys в SQLite выключен — ответы удаляем сами.
    db.execute(sa_delete(EventRsvp).where(EventRsvp.event_id == event.id))
    db.delete(event)
    db.commit()


def rsvps(db: Session, event_ids: list[int]) -> list[EventRsvp]:
    if not event_ids:
        return []
    query = (
        select(EventRsvp)
        .options(joinedload(EventRsvp.user))
        .where(EventRsvp.event_id.in_(event_ids))
    )
    return list(db.scalars(query))


def set_rsvp(db: Session, event_id: int, user_id: int, going: bool | None) -> None:
    row = db.get(EventRsvp, (event_id, user_id))
    if going is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(EventRsvp(event_id=event_id, user_id=user_id, going=going))
    else:
        row.going = going
    db.commit()
