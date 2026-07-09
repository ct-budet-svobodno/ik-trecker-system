from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.leadership_note import LeadershipNote


def list_all(db: Session) -> list[LeadershipNote]:
    query = (
        select(LeadershipNote)
        .options(joinedload(LeadershipNote.created_by))
        .order_by(LeadershipNote.created_at.desc())
    )
    return list(db.scalars(query))


def get_by_id(db: Session, note_id: int) -> LeadershipNote | None:
    return db.get(LeadershipNote, note_id)


def create(db: Session, *, title: str, body: str, created_by_id: int) -> LeadershipNote:
    note = LeadershipNote(title=title, body=body, created_by_id=created_by_id)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def delete(db: Session, note: LeadershipNote) -> None:
    db.delete(note)
    db.commit()
