from datetime import date

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.personal_todo import PersonalTodo


def list_for_day(db: Session, user_id: int, day: date) -> list[PersonalTodo]:
    query = (
        select(PersonalTodo)
        .where(PersonalTodo.user_id == user_id, PersonalTodo.date == day)
        .order_by(PersonalTodo.id)
    )
    return list(db.scalars(query))


def list_undone_before(db: Session, user_id: int, day: date) -> list[PersonalTodo]:
    query = (
        select(PersonalTodo)
        .where(
            PersonalTodo.user_id == user_id,
            PersonalTodo.date < day,
            PersonalTodo.done.is_(False),
        )
        .order_by(PersonalTodo.date, PersonalTodo.id)
    )
    return list(db.scalars(query))


def get_by_id(db: Session, todo_id: int) -> PersonalTodo | None:
    return db.get(PersonalTodo, todo_id)


def create(db: Session, *, user_id: int, day: date, title: str) -> PersonalTodo:
    todo = PersonalTodo(user_id=user_id, date=day, title=title)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


def update_fields(db: Session, todo: PersonalTodo, fields: dict) -> PersonalTodo:
    for key, value in fields.items():
        setattr(todo, key, value)
    db.commit()
    db.refresh(todo)
    return todo


def move_undone_before(db: Session, user_id: int, day: date) -> None:
    db.execute(
        update(PersonalTodo)
        .where(
            PersonalTodo.user_id == user_id,
            PersonalTodo.date < day,
            PersonalTodo.done.is_(False),
        )
        .values(date=day)
    )
    db.commit()


def delete(db: Session, todo: PersonalTodo) -> None:
    db.delete(todo)
    db.commit()
