"""Партии в морской бой: создание, приглашение, расстановка, выстрелы и бот.

Механика — app/games/seabattle.py; лобби устроено как у дурака
(см. durak_service): WAITING → READY_CHECK (оба жмут «Готов» за READY_SECONDS)
→ PLACING (каждый расставляет флот, без срока) → PLAYING → FINISHED.
С ботом партия сразу начинается с расстановки. Не успел подтвердить гость —
место снова свободно, создатель — CANCELLED; срок проверяется лениво (_expire).

Видимость: партию видят её игроки; чужую — только пока она ждёт соперника.
Чужой флот не отдаём: в ответе только выстрелы и потопленные корабли.
"""
import datetime
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.games import seabattle
from app.models.sea_battle_game import SeaBattleGame, SeaBattleStatus
from app.models.user import User
from app.repositories import sea_battle_game_repository
from app.schemas.sea_battle import SeaBattleMove
from app.services import push_service, telegram_service
from app.services.exceptions import (
    SeaBattleMoveError,
    SeaBattleNotFoundError,
    SeaBattleVersionConflictError,
)

BOT_NAME = "Бот"
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
READY_SECONDS = 5
READY_GRACE_SECONDS = 1.5
# Брошенное лобби не висит вечно: через сутки партия закрывается сама.
WAITING_TTL_HOURS = 24
INVITE_IMAGE_PATH = "/og/sea-invite.png"
START_PREFIX = "sea_"


def _now() -> datetime.datetime:
    """UTC без tz — в таком виде SQLite отдаёт ready_deadline обратно."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _naive_utc(value: datetime.datetime) -> datetime.datetime:
    """Привести дату из SQLite к UTC без tz — в одном виде с _now()."""
    return value.astimezone(datetime.UTC).replace(tzinfo=None) if value.tzinfo else value


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not sea_battle_game_repository.code_exists(db, code):
            return code


def _seat_of(game: SeaBattleGame, user: User) -> int | None:
    if game.host_id == user.id:
        return 0
    if game.guest_id is not None and game.guest_id == user.id:
        return 1
    return None


def _can_join(game: SeaBattleGame, user: User) -> bool:
    return (
        game.status == SeaBattleStatus.WAITING
        and game.guest_id is None
        and game.host_id != user.id
    )


def _waiting_expired(game: SeaBattleGame) -> bool:
    """Лобби, которое никто так и не открыл, живёт WAITING_TTL_HOURS часов."""
    return (
        game.status == SeaBattleStatus.WAITING
        and game.created_at is not None
        and _now() - _naive_utc(game.created_at) > datetime.timedelta(hours=WAITING_TTL_HOURS)
    )


def _expire(db: Session, game: SeaBattleGame) -> SeaBattleGame:
    if _waiting_expired(game):
        game = sea_battle_game_repository.save(
            db, game, status=SeaBattleStatus.CANCELLED, ready_deadline=None
        )
        _sync_chat(game)
        return game
    if game.status != SeaBattleStatus.READY_CHECK or _now() <= game.ready_deadline:
        return game
    if not game.host_ready:
        game = sea_battle_game_repository.save(
            db, game, status=SeaBattleStatus.CANCELLED, ready_deadline=None
        )
    else:
        game = sea_battle_game_repository.save(
            db,
            game,
            status=SeaBattleStatus.WAITING,
            guest_id=None,
            host_ready=False,
            guest_ready=False,
            ready_deadline=None,
        )
    _sync_chat(game)
    return game


def get_for(db: Session, user: User, code: str) -> SeaBattleGame:
    game = sea_battle_game_repository.get_by_code(db, code.upper())
    if game is not None:
        game = _expire(db, game)
    if game is None or (_seat_of(game, user) is None and not _can_join(game, user)):
        raise SeaBattleNotFoundError("Партия не найдена или места уже заняты")
    return game


def list_active(db: Session, user: User) -> list[SeaBattleGame]:
    games = [_expire(db, g) for g in sea_battle_game_repository.list_active_for(db, user.id)]
    return [
        g for g in games
        if g.status not in (SeaBattleStatus.FINISHED, SeaBattleStatus.CANCELLED)
        and _seat_of(g, user) is not None
    ]


def create(db: Session, user: User, vs_bot: bool) -> SeaBattleGame:
    state = seabattle.new_game()
    if vs_bot:
        state.boards[1].ships = seabattle.random_fleet()
    return sea_battle_game_repository.create(
        db,
        code=_new_code(db),
        host_id=user.id,
        vs_bot=vs_bot,
        status=SeaBattleStatus.PLACING if vs_bot else SeaBattleStatus.WAITING,
        state=state.to_dict(),
    )


def join(db: Session, user: User, code: str) -> SeaBattleGame:
    game = get_for(db, user, code)
    if _seat_of(game, user) is not None:
        return game
    game = sea_battle_game_repository.save(
        db,
        game,
        guest_id=user.id,
        status=SeaBattleStatus.READY_CHECK,
        host_ready=False,
        guest_ready=False,
        ready_deadline=_now() + datetime.timedelta(seconds=READY_SECONDS + READY_GRACE_SECONDS),
    )
    _sync_chat(game)
    push_service.send_to_user(
        db,
        game.host_id,
        title="Соперник нашёлся",
        body=f"{user.full_name} садится играть в морской бой — подтвердите участие за {READY_SECONDS} секунд",
        url=f"/games/sea/{game.code}",
    )
    return game


def ready(db: Session, user: User, code: str) -> SeaBattleGame:
    game = get_for(db, user, code)
    seat = _seat_of(game, user)
    if seat is None:
        raise SeaBattleMoveError("Вы не играете в этой партии")
    if game.status != SeaBattleStatus.READY_CHECK:
        return game
    flags = {"host_ready": True} if seat == 0 else {"guest_ready": True}
    both = (game.host_ready or seat == 0) and (game.guest_ready or seat == 1)
    if both:
        flags.update(
            status=SeaBattleStatus.PLACING, state=seabattle.new_game().to_dict(), ready_deadline=None
        )
    game = sea_battle_game_repository.save(db, game, **flags)
    if both:
        _sync_chat(game)
    return game


def cancel(db: Session, user: User, code: str) -> SeaBattleGame:
    """Закрыть лобби, пока никто не сел. Отменить идущую партию нельзя."""
    game = get_for(db, user, code)
    if _seat_of(game, user) != 0:
        raise SeaBattleMoveError("Закрыть партию может только создатель")
    if game.status == SeaBattleStatus.CANCELLED:
        return game
    if game.status != SeaBattleStatus.WAITING:
        raise SeaBattleMoveError("Партия уже началась — закрыть её нельзя")
    game = sea_battle_game_repository.save(
        db, game, status=SeaBattleStatus.CANCELLED, ready_deadline=None
    )
    _sync_chat(game)
    return game


def invite_to_chat(db: Session, user: User, code: str) -> SeaBattleGame:
    """Опубликовать приглашение в чате актива (один раз на партию)."""
    game = get_for(db, user, code)
    if _seat_of(game, user) != 0 or game.status != SeaBattleStatus.WAITING:
        raise SeaBattleMoveError("Позвать в чат может создатель, пока партия ждёт соперника")
    if not chat_invites_enabled():
        raise SeaBattleMoveError("Чат для приглашений не настроен")
    if game.message_id is not None:
        return game
    caption, buttons = _chat_message(game)
    photo = settings.webapp_url.rstrip("/") + INVITE_IMAGE_PATH
    message_id = telegram_service.send_photo(settings.telegram_games_chat_id, photo, caption, buttons)
    if message_id is None:
        raise SeaBattleMoveError("Не удалось отправить приглашение в чат")
    game.chat_id, game.message_id = settings.telegram_games_chat_id, message_id
    db.commit()
    db.refresh(game)
    return game


def chat_invites_enabled() -> bool:
    return telegram_service.telegram_enabled() and settings.telegram_games_chat_id is not None


def invite_url(game: SeaBattleGame) -> str:
    return telegram_service.startapp_url(f"{START_PREFIX}{game.code}") or (
        settings.webapp_url.rstrip("/") + f"/games/sea/{game.code}"
    )


def _chat_message(game: SeaBattleGame) -> tuple[str, list[dict] | None]:
    esc = telegram_service.escape
    host = esc(game.host.full_name)
    guest = esc(game.guest.full_name) if game.guest else None
    head = "🚢 <b>Морской бой</b> · классика 10×10"
    vs = f"<b>{host}</b> vs <b>{guest}</b>"
    if game.status == SeaBattleStatus.WAITING:
        text = f"{head}\n\n<b>{host}</b> ищет соперника.\nПервый, кто нажмёт кнопку, садится за стол."
        return text, [{"text": "Присоединиться", "url": invite_url(game)}]
    if game.status == SeaBattleStatus.READY_CHECK:
        return f"{head}\n\n{vs}\nПодтверждают участие…", None
    if game.status == SeaBattleStatus.PLACING:
        return f"{head}\n\n{vs}\nРасставляют корабли. Места заняты.", None
    if game.status == SeaBattleStatus.PLAYING:
        return f"{head}\n\n{vs}\nИдёт бой. Места заняты.", None
    if game.status == SeaBattleStatus.CANCELLED:
        return f"{head}\n\n<b>{host}</b> — партия отменена.", None
    state = seabattle.Game.from_dict(game.state)
    winner = host if state.winner == 0 else guest
    return f"{head}\n\n{vs}\n<b>{winner}</b> топит весь флот соперника.", None


def _sync_chat(game: SeaBattleGame) -> None:
    if game.chat_id is None or game.message_id is None:
        return
    caption, buttons = _chat_message(game)
    telegram_service.edit_caption(game.chat_id, game.message_id, caption, buttons)


def move(db: Session, user: User, code: str, payload: SeaBattleMove) -> SeaBattleGame:
    game = get_for(db, user, code)
    seat = _seat_of(game, user)
    if seat is None:
        raise SeaBattleMoveError("Вы не играете в этой партии")
    if game.status not in (SeaBattleStatus.PLACING, SeaBattleStatus.PLAYING):
        raise SeaBattleMoveError("Партия не идёт")
    # Расстановки игроков друг от друга не зависят: соперник, поставивший флот
    # раньше, поднял версию, но мою расстановку это не отменяет.
    if payload.action != "place" and payload.version != game.version:
        raise SeaBattleVersionConflictError("Соперник уже сходил — обновляем поле")

    state = seabattle.Game.from_dict(game.state)
    status = game.status
    try:
        if payload.action == "resign":
            seabattle.resign(state, seat)
        elif payload.action == "place":
            if status != SeaBattleStatus.PLACING:
                raise seabattle.IllegalMove("Флот уже в бою")
            seabattle.place_fleet(state, seat, payload.ships or [])
            if all(seabattle.placed(state, s) for s in (0, 1)):
                status = SeaBattleStatus.PLAYING
                if game.vs_bot:
                    seabattle.run_bot(state)  # бот мог получить первый выстрел
        else:
            if status != SeaBattleStatus.PLAYING:
                raise seabattle.IllegalMove("Сначала расставьте флот")
            if payload.cell is None:
                raise seabattle.IllegalMove("Не указана клетка")
            seabattle.fire(state, seat, payload.cell)
            if game.vs_bot:
                seabattle.run_bot(state)
    except seabattle.IllegalMove as exc:
        raise SeaBattleMoveError(str(exc)) from exc

    if state.over:
        status = SeaBattleStatus.FINISHED
    changed_stage = status != game.status
    game = sea_battle_game_repository.save(db, game, state=state.to_dict(), status=status)
    if changed_stage:
        _sync_chat(game)
    return game


def _turn_of(game: SeaBattleGame, state: seabattle.Game, seat: int) -> bool:
    if game.status == SeaBattleStatus.READY_CHECK:
        return not (game.host_ready if seat == 0 else game.guest_ready)
    if game.status == SeaBattleStatus.PLACING:
        return not seabattle.placed(state, seat)
    if game.status == SeaBattleStatus.PLAYING:
        return state.turn == seat
    return False


def is_my_turn(game: SeaBattleGame, user: User) -> bool:
    seat = _seat_of(game, user)
    if seat is None:
        return False
    return _turn_of(game, seabattle.Game.from_dict(game.state), seat)


def opponent_name(game: SeaBattleGame, user: User) -> str | None:
    if game.vs_bot:
        return BOT_NAME
    other = game.guest if game.host_id == user.id else game.host
    return other.full_name if other else None


def view(game: SeaBattleGame, user: User) -> dict:
    """Партия глазами игрока (или приглашённого) — под схему SeaBattleOut."""
    state = seabattle.Game.from_dict(game.state)
    seat = _seat_of(game, user)
    started = game.status in (SeaBattleStatus.PLACING, SeaBattleStatus.PLAYING, SeaBattleStatus.FINISHED)
    finished = game.status == SeaBattleStatus.FINISHED

    def fleet(idx: int) -> list[int]:
        board = state.boards[idx]
        return board.alive_sizes() if board.ships else list(seabattle.FLEET)

    def player(idx: int) -> dict | None:
        if idx == 1 and game.vs_bot:
            person_id, name = None, BOT_NAME
        else:
            person = game.host if idx == 0 else game.guest
            if person is None:
                return None
            person_id, name = person.id, person.full_name
        return {
            "id": person_id,
            "full_name": name,
            "placed": started and seabattle.placed(state, idx),
            "fleet": fleet(idx),
        }

    def board(idx: int, own: bool) -> dict:
        b = state.boards[idx]
        shooter = 1 - idx
        return {
            "ships": b.ships if own or finished else b.sunk_ships(),
            "shots": {str(c): r for c, r in b.shots.items()},
            "recent": [cell for who, cell in state.recent if who == shooter],
        }

    result = None
    if seat is not None and finished:
        result = "win" if state.winner == seat else "lose"

    ready = None
    if game.status == SeaBattleStatus.READY_CHECK and seat is not None:
        left = (game.ready_deadline - _now()).total_seconds() - READY_GRACE_SECONDS
        ready = {
            "me": game.host_ready if seat == 0 else game.guest_ready,
            "opponent": game.guest_ready if seat == 0 else game.host_ready,
            "seconds_left": max(0.0, min(float(READY_SECONDS), left)),
        }

    me_idx = seat if seat is not None else 1
    return {
        "code": game.code,
        "status": game.status,
        "vs_bot": game.vs_bot,
        "version": game.version,
        "seat": seat,
        "can_join": _can_join(game, user),
        "me": player(seat) if seat is not None else None,
        "opponent": player(1 - me_idx),
        "my_board": board(seat, own=True) if seat is not None and started else None,
        "enemy_board": board(1 - seat, own=False) if seat is not None and started else None,
        "my_turn": seat is not None and _turn_of(game, state, seat),
        "result": result,
        "ready": ready,
        "invite_url": invite_url(game) if game.status == SeaBattleStatus.WAITING else None,
        "chat_invite": {
            "available": seat == 0 and game.status == SeaBattleStatus.WAITING and chat_invites_enabled(),
            "sent": game.message_id is not None,
        },
    }
