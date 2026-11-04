from datetime import date

from sqlalchemy.orm import Session

from app.models.personal_todo import PersonalTodo
from app.models.user import User
from app.repositories import personal_todo_repository
from app.schemas.personal_todo import PersonalTodoCreate
from app.services.exceptions import PersonalTodoNotFoundError


def list_for_day(db: Session, viewer: User, day: date) -> list[PersonalTodo]:
    return personal_todo_repository.list_for_day(db, viewer.id, day)


def list_overdue(db: Session, viewer: User, before: date) -> list[PersonalTodo]:
    """Невыполненное из прошлых дней — чтобы предложить перенести на сегодня."""
    return personal_todo_repository.list_undone_before(db, viewer.id, before)


def create(db: Session, viewer: User, payload: PersonalTodoCreate) -> PersonalTodo:
    return personal_todo_repository.create(
        db, user_id=viewer.id, day=payload.date, title=payload.title.strip()
    )


def get_own(db: Session, viewer: User, todo_id: int) -> PersonalTodo:
    todo = personal_todo_repository.get_by_id(db, todo_id)
    # Чужой пункт для пользователя не существует: 404, а не 403 —
    # не раскрываем, что такой id вообще есть.
    if todo is None or todo.user_id != viewer.id:
        raise PersonalTodoNotFoundError("Пункт не найден")
    return todo


def update(db: Session, viewer: User, todo_id: int, fields: dict) -> PersonalTodo:
    todo = get_own(db, viewer, todo_id)
    if not fields:
        return todo
    return personal_todo_repository.update_fields(db, todo, fields)


def carry_over(db: Session, viewer: User, day: date) -> list[PersonalTodo]:
    personal_todo_repository.move_undone_before(db, viewer.id, day)
    return personal_todo_repository.list_for_day(db, viewer.id, day)


def delete(db: Session, viewer: User, todo_id: int) -> None:
    personal_todo_repository.delete(db, get_own(db, viewer, todo_id))
