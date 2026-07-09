from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.leadership_note import LeadershipNote
from app.models.user import User, UserRole
from app.repositories import leadership_note_repository
from app.schemas.leadership_note import LeadershipNoteCreate, LeadershipNoteOut

# Весь раздел доступен только руководителям и админу.
router = APIRouter(dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))])


@router.get("", response_model=list[LeadershipNoteOut])
def list_notes(db: Session = Depends(get_db)) -> list[LeadershipNote]:
    return leadership_note_repository.list_all(db)


@router.post("", response_model=LeadershipNoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: LeadershipNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadershipNote:
    return leadership_note_repository.create(
        db,
        title=payload.title,
        body=payload.body,
        created_by_id=current_user.id,
    )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)) -> None:
    note = leadership_note_repository.get_by_id(db, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    leadership_note_repository.delete(db, note)
