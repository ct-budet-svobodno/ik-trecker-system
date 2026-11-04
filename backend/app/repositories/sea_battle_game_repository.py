from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.sea_battle_game import SeaBattleGame, SeaBattleStatus


def _base_query():
    return select(SeaBattleGame).options(joinedload(SeaBattleGame.host), joinedload(SeaBattleGame.guest))


def get_by_code(db: Session, code: str) -> SeaBattleGame | None:
    return db.scalar(_base_query().where(SeaBattleGame.code == code))


def code_exists(db: Session, code: str) -> bool:
    return db.scalar(select(SeaBattleGame.id).where(SeaBattleGame.code == code)) is not None


def list_active_for(db: Session, user_id: int, limit: int = 20) -> list[SeaBattleGame]:
    query = (
        _base_query()
        .where(
            or_(SeaBattleGame.host_id == user_id, SeaBattleGame.guest_id == user_id),
            SeaBattleGame.status.not_in([SeaBattleStatus.FINISHED, SeaBattleStatus.CANCELLED]),
        )
        .order_by(SeaBattleGame.updated_at.desc(), SeaBattleGame.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def create(
    db: Session, *, code: str, host_id: int, vs_bot: bool, status: SeaBattleStatus, state: dict
) -> SeaBattleGame:
    game = SeaBattleGame(code=code, host_id=host_id, vs_bot=vs_bot, status=status, state=state, version=1)
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def save(db: Session, game: SeaBattleGame, **fields) -> SeaBattleGame:
    """Записать новое состояние и поднять версию (JSON присваиваем целиком,
    иначе SQLAlchemy не заметит изменений внутри словаря)."""
    for key, value in fields.items():
        setattr(game, key, value)
    game.version += 1
    db.commit()
    db.refresh(game)
    return game
