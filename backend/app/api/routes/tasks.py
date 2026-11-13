from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.task import TaskCommentCreate, TaskCommentOut, TaskCreate, TaskOut, TaskUpdate
from app.services import task_service
from app.services.exceptions import (
    PrivateTaskAccessError,
    TaskAccessError,
    TaskAssigneeError,
    TaskCommentNotFoundError,
    TaskFieldNotEditableError,
    TaskNotFoundError,
    TaskReminderError,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaskOut]:
    return [task_service.view(task, current_user) for task in task_service.list_tasks_for(db, current_user)]


@router.post(
    "",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    task_create: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskOut:
    if current_user.role == UserRole.EMPLOYEE and not task_create.is_checklist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    try:
        task = task_service.create_task(db, task_create, created_by=current_user)
    except (PrivateTaskAccessError, TaskAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TaskAssigneeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return task_service.view(task, current_user)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskOut:
    try:
        task = task_service.get_visible(db, current_user, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    try:
        task = task_service.update_task(db, task, task_update, current_user)
    except (TaskFieldNotEditableError, TaskAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TaskAssigneeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return task_service.view(task, current_user)


@router.post("/{task_id}/remind", response_model=TaskOut)
def remind_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskOut:
    """Автор поручения напоминает исполнителям, кто ещё не сделал."""
    try:
        task = task_service.get_visible(db, current_user, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    try:
        task = task_service.remind(db, task, current_user)
    except TaskReminderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return task_service.view(task, current_user)


def _visible_task(db: Session, user: User, task_id: int):
    try:
        return task_service.get_visible(db, user, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    task = _visible_task(db, current_user, task_id)
    try:
        task_service.delete_task(db, task, current_user)
    except TaskAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("/{task_id}/comments", response_model=list[TaskCommentOut])
def list_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.list_comments(db, _visible_task(db, current_user, task_id))


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    task_id: int,
    payload: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _visible_task(db, current_user, task_id)
    try:
        return task_service.add_comment(db, task, payload, current_user)
    except TaskAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TaskCommentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    task_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    task = _visible_task(db, current_user, task_id)
    try:
        task_service.delete_comment(db, task, comment_id, current_user)
    except TaskAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TaskCommentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
