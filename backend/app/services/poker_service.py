"""Persistence and access checks for private poker tables."""

import copy
import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.games import poker
from app.models.poker_game import PokerGame
from app.models.user import User

ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'


class PokerNotFoundError(ValueError):
    pass


class PokerConflictError(ValueError):
    pass


def _seat(game: PokerGame, user: User) -> int | None:
    return next((i for i, p in enumerate(game.state['players']) if p['id'] == user.id), None)


def _get(db: Session, code: str) -> PokerGame:
    game = db.scalar(select(PokerGame).where(PokerGame.code == code.upper()))
    if game is None:
        raise PokerNotFoundError('Стол не найден')
    return game


def get_for(db: Session, user: User, code: str) -> PokerGame:
    game = _get(db, code)
    if _seat(game, user) is None and (game.status != 'waiting' or len(game.state['players']) >= poker.MAX_PLAYERS):
        raise PokerNotFoundError('Стол не найден или игра уже началась')
    return game


def list_active(db: Session, user: User) -> list[PokerGame]:
    games = db.scalars(select(PokerGame).where(PokerGame.status.in_(['waiting', 'playing'])).order_by(PokerGame.id.desc())).all()
    return [game for game in games if _seat(game, user) is not None]


def list_open(db: Session, user: User) -> list[PokerGame]:
    games = db.scalars(select(PokerGame).where(PokerGame.status == 'waiting').order_by(PokerGame.id.desc())).all()
    return [game for game in games if _seat(game, user) is None and len(game.state['players']) < poker.MAX_PLAYERS]


def create(db: Session, user: User) -> PokerGame:
    while True:
        code = ''.join(secrets.choice(ALPHABET) for _ in range(6))
        if db.scalar(select(PokerGame.id).where(PokerGame.code == code)) is None:
            break
    state = {'players': [dict(id=user.id, name=user.full_name, stack=poker.START_STACK)], 'dealer': -1, 'phase': None}
    game = PokerGame(code=code, host_id=user.id, status='waiting', state=state, version=1)
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def _save(db: Session, game: PokerGame, state: dict, status: str | None = None) -> PokerGame:
    values = {'state': state, 'version': game.version + 1}
    if status:
        values['status'] = status
    result = db.execute(update(PokerGame).where(PokerGame.id == game.id, PokerGame.version == game.version).values(**values))
    if result.rowcount != 1:
        db.rollback()
        raise PokerConflictError('Стол изменился. Обновите страницу')
    db.commit()
    db.refresh(game)
    return game


def join(db: Session, user: User, code: str) -> PokerGame:
    game = get_for(db, user, code)
    if _seat(game, user) is not None:
        return game
    if game.status != 'waiting' or len(game.state['players']) >= poker.MAX_PLAYERS:
        raise poker.IllegalMove('В лобби больше нет мест')
    state = copy.deepcopy(game.state)
    state['players'].append(dict(id=user.id, name=user.full_name, stack=poker.START_STACK))
    return _save(db, game, state)


def leave(db: Session, user: User, code: str) -> PokerGame:
    game = get_for(db, user, code)
    seat = _seat(game, user)
    if seat is None or game.status != 'waiting':
        raise poker.IllegalMove('Из начатой партии выйти нельзя')
    if game.host_id == user.id:
        return _save(db, game, game.state, 'cancelled')
    state = copy.deepcopy(game.state)
    state['players'].pop(seat)
    return _save(db, game, state)


def start(db: Session, user: User, code: str) -> PokerGame:
    game = get_for(db, user, code)
    if game.host_id != user.id or game.status != 'waiting':
        raise poker.IllegalMove('Начать партию может только создатель лобби')
    state = copy.deepcopy(game.state)
    poker.new_hand(state)
    return _save(db, game, state, 'playing')


def stop(db: Session, user: User, code: str) -> PokerGame:
    game = get_for(db, user, code)
    if game.host_id != user.id or game.status != 'playing':
        raise poker.IllegalMove('Остановить партию может только создатель стола')
    return _save(db, game, game.state, 'cancelled')


def next_hand(db: Session, user: User, code: str, version: int) -> PokerGame:
    game = get_for(db, user, code)
    if game.version != version:
        raise PokerConflictError('Стол изменился. Обновите страницу')
    if game.host_id != user.id or game.status != 'playing':
        raise poker.IllegalMove('Новую раздачу начинает создатель стола')
    state = copy.deepcopy(game.state)
    poker.new_hand(state)
    return _save(db, game, state)


def move(db: Session, user: User, code: str, version: int, action: str, amount: int | None) -> PokerGame:
    game = get_for(db, user, code)
    if game.version != version:
        raise PokerConflictError('Стол изменился. Обновите страницу')
    seat = _seat(game, user)
    if seat is None or game.status != 'playing':
        raise poker.IllegalMove('Вы не играете за этим столом')
    state = copy.deepcopy(game.state)
    poker.move(state, seat, action, amount)
    return _save(db, game, state)


def view(game: PokerGame, user: User) -> dict:
    state = game.state
    seat = _seat(game, user)
    phase = state.get('phase')
    players = []
    for i, p in enumerate(state['players']):
        cards = p.get('cards', [])
        if phase != 'showdown' and i != seat:
            cards = [None] * len(cards)
        elif phase == 'showdown' and p.get('folded') and i != seat:
            cards = [None] * len(cards)
        players.append({key: value for key, value in p.items() if key != 'cards'} | {'seat': i, 'cards': cards})
    mine = state['players'][seat] if seat is not None else None
    return {
        'code': game.code, 'status': game.status, 'version': game.version,
        'host_id': game.host_id, 'seat': seat, 'is_host': game.host_id == user.id,
        'can_join': game.status == 'waiting' and seat is None and len(players) < poker.MAX_PLAYERS,
        'min_players': poker.MIN_PLAYERS, 'max_players': poker.MAX_PLAYERS,
        'players': players, 'phase': phase, 'board': state.get('board', []),
        'dealer': state.get('dealer'), 'turn': state.get('turn'),
        'pot': sum(p.get('invested', 0) for p in state['players']) if phase != 'showdown' else 0,
        'current_bet': state.get('current_bet', 0),
        'min_raise': state.get('min_raise', poker.BIG_BLIND),
        'can_continue': sum(p['stack'] > 0 for p in state['players']) >= poker.MIN_PLAYERS,
        'to_call': max(0, state.get('current_bet', 0) - mine.get('bet', 0)) if mine else 0,
        'result': state.get('result'),
        'invite_url': f'{settings.webapp_url.rstrip("/")}/games/poker/{game.code}',
    }
