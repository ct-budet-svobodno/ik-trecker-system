from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.task import Task, TaskPriority
from app.models.user import User, UserRole


def _base_query():
    return select(Task).options(
        joinedload(Task.direction),
        joinedload(Task.assignee),
        joinedload(Task.created_by),
    )


def list_visible_for(db: Session, viewer: User) -> list[Task]:
    query = _base_query().order_by(Task.created_at.desc())
    if viewer.role == UserRole.EMPLOYEE:
        query = query.where(
            (Task.assignee_id.is_(None)) | (Task.assignee.has(User.role != UserRole.MANAGER))
        )
    return list(db.scalars(query).unique())


def get_by_id(db: Session, task_id: int) -> Task | None:
    return db.scalar(_base_query().where(Task.id == task_id))


def create(
    db: Session,
    *,
    title: str,
    description: str,
    direction_id: int,
    priority: TaskPriority,
    assignee_id: int | None,
    due_date: date | None,
    created_by_id: int,
) -> Task:
    task = Task(
        title=title,
        description=description,
        direction_id=direction_id,
        priority=priority,
        assignee_id=assignee_id,
        due_date=due_date,
        created_by_id=created_by_id,
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
