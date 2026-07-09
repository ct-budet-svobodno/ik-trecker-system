from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.leadership_task import LeadershipTask
from app.models.user import User, UserRole
from app.repositories import leadership_task_repository
from app.services import leadership_task_service
from app.services.exceptions import DirectionNotFoundError, LeadershipAccessError
from app.schemas.leadership_task import (
    LeadershipTaskCreate,
    LeadershipTaskOut,
    LeadershipTaskUpdate,
)

# Раздел только для руководства и руководителей направлений.
# Сотрудники доступа не имеют — записи нигде в общей системе не видны.
router = APIRouter(dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))])


@router.get("", response_model=list[LeadershipTaskOut])
def list_tasks(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
) -> list[LeadershipTask]:
    return leadership_task_service.list_in_range(db, date_from, date_to)


@router.post("", response_model=LeadershipTaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: LeadershipTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadershipTask:
    try:
        return leadership_task_service.create(
            db,
            current_user,
            title=payload.title,
            direction_id=payload.direction_id,
            position=payload.position,
            task_date=payload.date,
            status=payload.status,
        )
    except DirectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except LeadershipAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.patch("/{task_id}", response_model=LeadershipTaskOut)
def update_task(
    task_id: int,
    payload: LeadershipTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadershipTask:
    task = leadership_task_repository.get_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    try:
        return leadership_task_service.update(
            db,
            current_user,
            task,
            {"title": payload.title, "date": payload.date, "status": payload.status},
        )
    except LeadershipAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    task = leadership_task_repository.get_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    try:
        leadership_task_service.delete(db, current_user, task)
    except LeadershipAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
