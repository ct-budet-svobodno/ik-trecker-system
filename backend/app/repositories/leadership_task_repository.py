from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.leadership_task import LeadershipTask, LeadershipTaskStatus
from app.models.user import LeadershipPosition


def _base_query():
    return select(LeadershipTask).options(
        joinedload(LeadershipTask.direction),
        joinedload(LeadershipTask.created_by),
    )


def list_in_range(db: Session, date_from: date, date_to: date) -> list[LeadershipTask]:
    # Блок виден, если его интервал [date … end_date] пересекает окно недели.
    # У одиночной записи end_date=NULL — берём date через COALESCE.
    end = func.coalesce(LeadershipTask.end_date, LeadershipTask.date)
    query = (
        _base_query()
        .where(LeadershipTask.date <= date_to, end >= date_from)
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
    is_editorial: bool,
    date: date,
    status: LeadershipTaskStatus,
    created_by_id: int,
    end_date: date | None = None,
    position_end: LeadershipPosition | None = None,
    color: str | None = None,
) -> LeadershipTask:
    task = LeadershipTask(
        title=title,
        direction_id=direction_id,
        position=position,
        is_editorial=is_editorial,
        date=date,
        status=status,
        created_by_id=created_by_id,
        end_date=end_date,
        position_end=position_end,
        color=color,
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
