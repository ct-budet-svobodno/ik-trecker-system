from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.user import User
from app.repositories import event_repository
from app.schemas.event import EventCreate, EventUpdate


def list_events(db: Session) -> list[Event]:
    return event_repository.list_all(db)


def create_event(db: Session, event_create: EventCreate, created_by: User) -> Event:
    return event_repository.create(
        db,
        title=event_create.title,
        description=event_create.description,
        location=event_create.location,
        start_at=event_create.start_at,
        end_at=event_create.end_at,
        created_by_id=created_by.id,
    )


def update_event(db: Session, event: Event, event_update: EventUpdate) -> Event:
    fields = event_update.model_dump(exclude_unset=True)
    return event_repository.update_fields(db, event, fields)


def delete_event(db: Session, event: Event) -> None:
    event_repository.delete(db, event)
