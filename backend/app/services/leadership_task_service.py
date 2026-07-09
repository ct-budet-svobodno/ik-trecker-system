from datetime import date

from sqlalchemy.orm import Session

from app.models.leadership_task import LeadershipTask, LeadershipTaskStatus
from app.models.user import LeadershipPosition, User, UserRole
from app.repositories import direction_repository, leadership_task_repository, user_repository
from app.services import push_service
from app.services.exceptions import (
    DirectionNotFoundError,
    LeadershipAccessError,
)


def is_leadership(user: User) -> bool:
    """Тройка или админ — полный доступ ко всем строкам таймлайна."""
    return user.role == UserRole.ADMIN or user.leadership_position is not None


def _ensure_can_edit_target(
    db: Session, viewer: User, direction_id: int | None, position: LeadershipPosition | None
) -> None:
    # Строки тройки (position) редактирует только руководство.
    if position is not None:
        if is_leadership(viewer):
            return
        raise LeadershipAccessError("Только руководство может ставить задачи тройке")
    # Строки направлений: руководство — любые, руководитель — только свои.
    if is_leadership(viewer):
        return
    if direction_id in direction_repository.list_ids_headed_by(db, viewer.id):
        return
    raise LeadershipAccessError("Недостаточно прав для этого направления")


def list_in_range(db: Session, date_from: date, date_to: date) -> list[LeadershipTask]:
    return leadership_task_repository.list_in_range(db, date_from, date_to)


def create(
    db: Session,
    viewer: User,
    *,
    title: str,
    direction_id: int | None,
    position: LeadershipPosition | None,
    task_date: date,
    status: LeadershipTaskStatus,
) -> LeadershipTask:
    if direction_id is not None and direction_repository.get_by_id(db, direction_id) is None:
        raise DirectionNotFoundError(f"Направление с id={direction_id} не найдено")
    _ensure_can_edit_target(db, viewer, direction_id, position)
    task = leadership_task_repository.create(
        db,
        title=title,
        direction_id=direction_id,
        position=position,
        date=task_date,
        status=status,
        created_by_id=viewer.id,
    )
    _notify_task_owners(db, viewer, task)
    return task


def _notify_task_owners(db: Session, actor: User, task: LeadershipTask) -> None:
    """Пуш тем, кому адресована строка: руководителям направления или держателю должности."""
    if task.direction_id is not None:
        direction = direction_repository.get_by_id(db, task.direction_id)
        targets = [h.id for h in (direction.heads if direction else []) if h.id != actor.id]
    else:
        targets = [
            u.id
            for u in user_repository.list_all(db)
            if u.leadership_position == task.position and u.id != actor.id
        ]
    push_service.send_to_users(
        db,
        targets,
        title="Задача от руководства",
        body=task.title,
        url="/leadership-timeline",
    )


def update(db: Session, viewer: User, task: LeadershipTask, fields: dict) -> LeadershipTask:
    _ensure_can_edit_target(db, viewer, task.direction_id, task.position)
    clean = {k: v for k, v in fields.items() if v is not None}
    if not clean:
        return task
    return leadership_task_repository.update_fields(db, task, clean)


def delete(db: Session, viewer: User, task: LeadershipTask) -> None:
    _ensure_can_edit_target(db, viewer, task.direction_id, task.position)
    leadership_task_repository.delete(db, task)
