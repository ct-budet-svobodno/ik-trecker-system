from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.bunker_game import BunkerGame, BunkerPlayer, BunkerStatus


def _base_query():
    return select(BunkerGame).options(
        joinedload(BunkerGame.host),
        selectinload(BunkerGame.players).joinedload(BunkerPlayer.user),
    )


def get_by_code(db: Session, code: str) -> BunkerGame | None:
    return db.scalar(_base_query().where(BunkerGame.code == code))


def code_exists(db: Session, code: str) -> bool:
    return db.scalar(select(BunkerGame.id).where(BunkerGame.code == code)) is not None


def list_active_for(db: Session, user_id: int, limit: int = 20) -> list[BunkerGame]:
    # Ведущий стола может сам не играть — его столы тоже в списке.
    playing = select(BunkerPlayer.game_id).where(BunkerPlayer.user_id == user_id)
    query = (
        _base_query()
        .where(
            or_(BunkerGame.id.in_(playing), BunkerGame.host_id == user_id),
            BunkerGame.status.in_([BunkerStatus.WAITING, BunkerStatus.PLAYING]),
        )
        .order_by(BunkerGame.updated_at.desc(), BunkerGame.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query).unique())


def list_tables(db: Session, limit: int = 50) -> list[BunkerGame]:
    query = (
        _base_query()
        .where(BunkerGame.title.is_not(None), BunkerGame.status != BunkerStatus.CANCELLED)
        .order_by(BunkerGame.created_at.desc(), BunkerGame.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query).unique())


def create(
    db: Session, *, code: str, host_id: int, player_ids: list[int], title: str | None = None
) -> BunkerGame:
    game = BunkerGame(code=code, host_id=host_id, title=title, status=BunkerStatus.WAITING, version=1)
    for seat, user_id in enumerate(player_ids):
        game.players.append(BunkerPlayer(user_id=user_id, seat=seat))
    db.add(game)
    db.commit()
    return get_by_code(db, code)


def add_player(db: Session, game: BunkerGame, user_id: int) -> BunkerGame:
    game.players.append(BunkerPlayer(user_id=user_id, seat=len(game.players)))
    return save(db, game)


def remove_player(db: Session, game: BunkerGame, user_id: int) -> BunkerGame:
    """Выйти из лобби: места остальных сдвигаются, чтобы шли подряд."""
    game.players = [p for p in game.players if p.user_id != user_id]
    db.flush()
    for seat, player in enumerate(game.players):
        player.seat = seat
    return save(db, game)


def set_players(db: Session, game: BunkerGame, user_ids: list[int], **fields) -> BunkerGame:
    """Заменить состав стола целиком (порядок списка — места)."""
    game.players = []
    db.flush()
    for seat, user_id in enumerate(user_ids):
        game.players.append(BunkerPlayer(user_id=user_id, seat=seat))
    return save(db, game, **fields)


def save(db: Session, game: BunkerGame, **fields) -> BunkerGame:
    """Записать новое состояние и поднять версию (JSON присваиваем целиком,
    иначе SQLAlchemy не заметит изменений внутри словаря)."""
    for key, value in fields.items():
        setattr(game, key, value)
    game.version += 1
    db.commit()
    db.refresh(game)
    return game
