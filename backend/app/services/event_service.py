from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.user import User, UserRole
from app.repositories import event_repository
from app.schemas.event import EventCreate, EventOut, EventUpdate


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


# ── «Приду / Не приду» ──

def with_rsvps(db: Session, events: list[Event], user: User) -> list[dict]:
    """Мероприятия для ответа API: свой ответ, счётчики и (админам) кто как ответил."""
    show_names = user.role == UserRole.ADMIN
    by_event: dict[int, list] = {}
    for rsvp in event_repository.rsvps(db, [e.id for e in events]):
        by_event.setdefault(rsvp.event_id, []).append(rsvp)
    result = []
    for event in events:
        rows = sorted(by_event.get(event.id, []), key=lambda r: r.user.full_name.lower())
        mine = next((r for r in rows if r.user_id == user.id), None)
        going = [{"id": r.user_id, "full_name": r.user.full_name} for r in rows if r.going]
        not_going = [{"id": r.user_id, "full_name": r.user.full_name} for r in rows if not r.going]
        result.append({
            **EventOut.model_validate(event).model_dump(),
            "my_rsvp": None if mine is None else ("going" if mine.going else "not_going"),
            "going_count": len(going),
            "not_going_count": len(not_going),
            "going": going if show_names else [],
            "not_going": not_going if show_names else [],
        })
    return result


def set_rsvp(db: Session, event: Event, user: User, status: str | None) -> None:
    going = None if status is None else status == "going"
    event_repository.set_rsvp(db, event.id, user.id, going)
