from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.personal_todo import PersonalTodo
from app.models.user import User
from app.schemas.personal_todo import (
    PersonalTodoCarryOver,
    PersonalTodoCreate,
    PersonalTodoOut,
    PersonalTodoUpdate,
)
from app.services import personal_todo_service
from app.services.exceptions import PersonalTodoNotFoundError

# Личный список на день: доступен любому авторизованному, но только свой.
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PersonalTodoOut])
def list_todos(
    day: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PersonalTodo]:
    return personal_todo_service.list_for_day(db, current_user, day)


@router.get("/overdue", response_model=list[PersonalTodoOut])
def list_overdue(
    before: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PersonalTodo]:
    return personal_todo_service.list_overdue(db, current_user, before)


@router.post("", response_model=PersonalTodoOut, status_code=status.HTTP_201_CREATED)
def create_todo(
    payload: PersonalTodoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonalTodo:
    return personal_todo_service.create(db, current_user, payload)


@router.post("/carry-over", response_model=list[PersonalTodoOut])
def carry_over(
    payload: PersonalTodoCarryOver,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PersonalTodo]:
    return personal_todo_service.carry_over(db, current_user, payload.date)


@router.patch("/{todo_id}", response_model=PersonalTodoOut)
def update_todo(
    todo_id: int,
    payload: PersonalTodoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonalTodo:
    fields = payload.model_dump(exclude_unset=True, exclude_none=True)
    try:
        return personal_todo_service.update(db, current_user, todo_id, fields)
    except PersonalTodoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        personal_todo_service.delete(db, current_user, todo_id)
    except PersonalTodoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
