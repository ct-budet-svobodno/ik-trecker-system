from datetime import date

from sqlalchemy import delete, select, true
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.direction import direction_heads
from app.models.task import Task, TaskAssignee, TaskComment, TaskPriority, TaskStatus
from app.models.user import User, UserRole


def _base_query():
    return select(Task).options(
        joinedload(Task.direction),
        joinedload(Task.assignee),
        joinedload(Task.created_by),
        selectinload(Task.assignees).joinedload(TaskAssignee.user),
        selectinload(Task.comments),
    )


def _visible_to(viewer: User, sees_all_private: bool):
    """Личное поручение видят автор и его исполнители; остальные — только если
    сервис разрешил видеть все поручения (админы и секретарь).

    Активист (employee) не видит ТЗ, выданные руководителям, — ни в списке,
    ни по прямому номеру задачи."""
    if sees_all_private:
        visible = true()
    else:
        visible = (
            Task.is_private.is_(False)
            | (Task.assignee_id == viewer.id)
            | (Task.created_by_id == viewer.id)
            | Task.assignees.any(TaskAssignee.user_id == viewer.id)
        )
    if viewer.role == UserRole.EMPLOYEE:
        visible = visible & (
            Task.assignee_id.is_(None)
            | (Task.assignee_id == viewer.id)
            | Task.assignee.has(User.role != UserRole.MANAGER)
        )
    return visible


def list_visible_for(db: Session, viewer: User, *, sees_all_private: bool = False) -> list[Task]:
    query = (
        _base_query()
        .where(_visible_to(viewer, sees_all_private))
        .order_by(Task.created_at.desc())
    )
    return list(db.scalars(query).unique())


def get_by_id(db: Session, task_id: int) -> Task | None:
    return db.scalar(_base_query().where(Task.id == task_id))


def get_visible(
    db: Session, viewer: User, task_id: int, *, sees_all_private: bool = False
) -> Task | None:
    return db.scalar(
        _base_query().where(Task.id == task_id, _visible_to(viewer, sees_all_private))
    )


def create(
    db: Session,
    *,
    title: str,
    description: str,
    direction_id: int | None,
    priority: TaskPriority,
    assignee_id: int | None,
    due_date: date | None,
    created_by_id: int,
    is_private: bool = False,
) -> Task:
    task = Task(
        title=title,
        description=description,
        direction_id=direction_id,
        priority=priority,
        assignee_id=assignee_id,
        due_date=due_date,
        created_by_id=created_by_id,
        is_private=is_private,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_fields(db: Session, task: Task, fields: dict) -> Task:
    for key, value in fields.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def set_assignees(db: Session, task: Task, user_ids: list[int]) -> list[int]:
    """Исполнители поручения ровно user_ids: оставшиеся сохраняют свой статус,
    новые начинают с «Новой». Возвращает id добавленных (их надо уведомить)."""
    keep = {a.user_id: a for a in task.assignees}
    added = [uid for uid in user_ids if uid not in keep]
    task.assignees = [keep.get(uid) or TaskAssignee(user_id=uid, status=TaskStatus.TODO) for uid in user_ids]
    task.assignee_id = user_ids[0] if user_ids else None
    return added


def users_exist(db: Session, user_ids: list[int]) -> bool:
    found = db.scalars(select(User.id).where(User.id.in_(user_ids), User.is_active.is_(True)))
    return set(found) == set(user_ids)


def heads_direction(db: Session, user_id: int, direction_id: int | None) -> bool:
    if direction_id is None:
        return False
    row = db.execute(
        select(direction_heads.c.user_id).where(
            direction_heads.c.user_id == user_id, direction_heads.c.direction_id == direction_id
        )
    ).first()
    return row is not None


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


# ── Комментарии ──

def list_comments(db: Session, task_id: int) -> list[TaskComment]:
    query = (
        select(TaskComment)
        .options(joinedload(TaskComment.author))
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.id)
    )
    return list(db.scalars(query))


def get_comment(db: Session, task_id: int, comment_id: int) -> TaskComment | None:
    return db.scalar(
        select(TaskComment)
        .options(joinedload(TaskComment.author))
        .where(TaskComment.id == comment_id, TaskComment.task_id == task_id)
    )


def add_comment(db: Session, task: Task, author_id: int, body: str, parent_id: int | None) -> TaskComment:
    comment = TaskComment(task_id=task.id, author_id=author_id, body=body, parent_id=parent_id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, comment: TaskComment) -> None:
    # Вместе с ответами: внешние ключи SQLite по умолчанию не каскадят.
    db.execute(delete(TaskComment).where(TaskComment.parent_id == comment.id))
    db.delete(comment)
    db.commit()
