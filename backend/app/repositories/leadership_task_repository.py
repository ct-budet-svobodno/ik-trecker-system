from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.leadership_task import LeadershipTask, LeadershipTaskStatus
from app.models.user import LeadershipPosition


def _base_query():
    return select(LeadershipTask).options(
        joinedload(LeadershipTask.direction),
        joinedload(LeadershipTask.created_by),
    )


def list_in_range(db: Session, date_from: date, date_to: date) -> list[LeadershipTask]:
    query = (
        _base_query()
        .where(LeadershipTask.date >= date_from, LeadershipTask.date <= date_to)
        .order_by(LeadershipTask.date, LeadershipTask.id)
    )
    return list(db.scalars(query).unique())


def get_by_id(db: Session, task_id: int) -> LeadershipTask | None:
    return db.scalar(_base_query().where(LeadershipTask.id == task_id))


def create(
    db: Session,
    *,
    title: str,
    direction_id: int | None,
    position: LeadershipPosition | None,
    date: date,
    status: LeadershipTaskStatus,
    created_by_id: int,
) -> LeadershipTask:
    task = LeadershipTask(
        title=title,
        direction_id=direction_id,
        position=position,
        date=date,
        status=status,
        created_by_id=created_by_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_fields(db: Session, task: LeadershipTask, fields: dict) -> LeadershipTask:
    for key, value in fields.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def delete(db: Session, task: LeadershipTask) -> None:
    db.delete(task)
    db.commit()
