from datetime import date

from sqlalchemy.orm import Session

from app.models.leadership_task import LeadershipTask, LeadershipTaskStatus
from app.models.user import LeadershipPosition, User, UserRole
from app.repositories import direction_repository, leadership_task_repository, user_repository
from app.schemas.leadership_task import POSITION_ORDER
from app.services import editorial_service, push_service
from app.services.exceptions import (
    DirectionNotFoundError,
    LeadershipAccessError,
)


def is_leadership(user: User) -> bool:
    """Тройка или админ — полный доступ ко всем строкам таймлайна."""
    return user.role == UserRole.ADMIN or user.leadership_position is not None


def _ensure_can_edit_target(
    db: Session,
    viewer: User,
    direction_id: int | None,
    position: LeadershipPosition | None,
    is_editorial: bool = False,
) -> None:
    # Строки тройки (position) редактирует только руководство.
    if position is not None:
        if is_leadership(viewer):
            return
        raise LeadershipAccessError("Только руководство может ставить задачи тройке")
    # Строка Редакции — общая для руководителей СМИ и Дизайна.
    if is_editorial:
        if is_leadership(viewer) or editorial_service.is_editor(db, viewer):
            return
        raise LeadershipAccessError("Задачи Редакции ведут руководство и редакторы")
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
    is_editorial: bool,
    task_date: date,
    status: LeadershipTaskStatus,
    end_date: date | None = None,
    position_end: LeadershipPosition | None = None,
    color: str | None = None,
) -> LeadershipTask:
    if direction_id is not None and direction_repository.get_by_id(db, direction_id) is None:
        raise DirectionNotFoundError(f"Направление с id={direction_id} не найдено")
    _ensure_can_edit_target(db, viewer, direction_id, position, is_editorial)
    task = leadership_task_repository.create(
        db,
        title=title,
        direction_id=direction_id,
        position=position,
        is_editorial=is_editorial,
        date=task_date,
        status=status,
        created_by_id=viewer.id,
        end_date=end_date,
        position_end=position_end,
        color=color,
    )
    _notify_task_owners(db, viewer, task)
    return task


def _covered_positions(task: LeadershipTask) -> list[LeadershipPosition]:
    """Должности, которые накрывает блок четвёрки: от position до position_end."""
    if task.position is None:
        return []
    if task.position_end is None:
        return [task.position]
    start = POSITION_ORDER.index(task.position)
    end = POSITION_ORDER.index(task.position_end)
    return POSITION_ORDER[start : end + 1]


def _editorial_head_ids(db: Session) -> set[int]:
    """id руководителей СМИ и Дизайна — адресаты строки Редакции."""
    ids: set[int] = set()
    for code in (editorial_service.SMI_SHORT_CODE, editorial_service.DESIGN_SHORT_CODE):
        dir_id = direction_repository.get_id_by_short_code(db, code)
        direction = direction_repository.get_by_id(db, dir_id) if dir_id else None
        ids.update(h.id for h in (direction.heads if direction else []))
    return ids


def _notify_task_owners(db: Session, actor: User, task: LeadershipTask) -> None:
    """Пуш тем, кому адресована строка: руководителям направления,
    держателю должности или руководителям СМИ и Дизайна (Редакция)."""
    if task.is_editorial:
        targets = [uid for uid in _editorial_head_ids(db) if uid != actor.id]
    elif task.direction_id is not None:
        direction = direction_repository.get_by_id(db, task.direction_id)
        targets = [h.id for h in (direction.heads if direction else []) if h.id != actor.id]
    else:
        covered = _covered_positions(task)
        targets = [
            u.id
            for u in user_repository.list_all(db)
            if u.leadership_position in covered and u.id != actor.id
        ]
    push_service.send_to_users(
        db,
        targets,
        title="Задача от руководства",
        body=task.title,
        url="/leadership-timeline",
    )


def update(db: Session, viewer: User, task: LeadershipTask, fields: dict) -> LeadershipTask:
    """Обновляет только переданные поля. Значение None означает «очистить»
    (напр. снять цвет), поэтому фильтрацию None делает вызывающий роут —
    он кладёт сюда лишь явно заданные клиентом поля."""
    _ensure_can_edit_target(db, viewer, task.direction_id, task.position, task.is_editorial)
    if not fields:
        return task
    return leadership_task_repository.update_fields(db, task, fields)


def delete(db: Session, viewer: User, task: LeadershipTask) -> None:
    _ensure_can_edit_target(db, viewer, task.direction_id, task.position, task.is_editorial)
    leadership_task_repository.delete(db, task)
