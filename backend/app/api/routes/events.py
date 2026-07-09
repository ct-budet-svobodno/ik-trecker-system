from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.event import Event
from app.models.user import User, UserRole
from app.repositories import event_repository
from app.schemas.event import EventCreate, EventOut, EventUpdate
from app.services import event_service

router = APIRouter(dependencies=[Depends(get_current_user)])


def _get_event_or_404(db: Session, event_id: int) -> Event:
    event = event_repository.get_by_id(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    return event


@router.get("", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)) -> list[Event]:
    return event_service.list_events(db)


@router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))],
)
def create_event(
    event_create: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Event:
    return event_service.create_event(db, event_create, created_by=current_user)


@router.patch(
    "/{event_id}",
    response_model=EventOut,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))],
)
def update_event(event_id: int, event_update: EventUpdate, db: Session = Depends(get_db)) -> Event:
    event = _get_event_or_404(db, event_id)
    return event_service.update_event(db, event, event_update)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))],
)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> None:
    event = _get_event_or_404(db, event_id)
    event_service.delete_event(db, event)
