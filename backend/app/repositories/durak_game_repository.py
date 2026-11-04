from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.durak_game import DurakGame, DurakGameStatus


def _base_query():
    return select(DurakGame).options(joinedload(DurakGame.host), joinedload(DurakGame.guest))


def get_by_code(db: Session, code: str) -> DurakGame | None:
    return db.scalar(_base_query().where(DurakGame.code == code))


def code_exists(db: Session, code: str) -> bool:
    return db.scalar(select(DurakGame.id).where(DurakGame.code == code)) is not None


def list_active_for(db: Session, user_id: int, limit: int = 20) -> list[DurakGame]:
    query = (
        _base_query()
        .where(
            or_(DurakGame.host_id == user_id, DurakGame.guest_id == user_id),
            DurakGame.status.not_in([DurakGameStatus.FINISHED, DurakGameStatus.CANCELLED]),
        )
        .order_by(DurakGame.updated_at.desc(), DurakGame.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def create(db: Session, *, code: str, host_id: int, vs_bot: bool, status: DurakGameStatus, state: dict) -> DurakGame:
    game = DurakGame(code=code, host_id=host_id, vs_bot=vs_bot, status=status, state=state, version=1)
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def save(db: Session, game: DurakGame, **fields) -> DurakGame:
    """Записать новое состояние и поднять версию (JSON присваиваем целиком,
    иначе SQLAlchemy не заметит изменений внутри словаря)."""
    for key, value in fields.items():
        setattr(game, key, value)
    game.version += 1
    db.commit()
    db.refresh(game)
    return game
