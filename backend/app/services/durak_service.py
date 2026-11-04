"""Партии в дурака: создание, приглашение, подтверждение участия, ходы и бот.

Механика — app/games/durak.py; здесь доступ, очерёдность и сохранение.

Жизнь партии с человеком:
  WAITING     — создатель ждёт; приглашение можно опубликовать в чате актива.
                Если за LOBBY_TTL_MINUTES минут второй не вошёл, лобби
                закрывается само (CANCELLED).
  READY_CHECK — второй нажал «Присоединиться»: место за ним, больше никто не
                войдёт. Оба жмут «Готов» без ограничения по времени; до старта
                гость может выйти, а создатель — закрыть лобби.
  PLAYING     — оба готовы, раздали карты.
  FINISHED / CANCELLED — сыграно / лобби закрыто.
Срок лобби проверяется лениво — при любом обращении к партии (см. _expire),
отдельного таймера нет.

Видимость: партию видят её игроки; чужую — только пока она ждёт соперника.
Остальным партия «не существует» — 404.
"""
import datetime
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.games import durak
from app.models.durak_game import DurakGame, DurakGameStatus
from app.models.user import User
from app.repositories import durak_game_repository
from app.schemas.durak import DurakMove
from app.services import push_service, telegram_service
from app.services.exceptions import (
    DurakGameNotFoundError,
    DurakMoveError,
    DurakVersionConflictError,
)

BOT_NAME = "Бот"
# Без похожих символов (0/O, 1/I/L): код могут продиктовать голосом.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
# Брошенное лобби не висит вечно: если второй не пришёл за это время,
# комната закрывается сама.
LOBBY_TTL_MINUTES = 5
INVITE_IMAGE_PATH = "/og/durak-invite.png"


def _now() -> datetime.datetime:
    """UTC без tz — в таком виде SQLite отдаёт даты обратно."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _naive_utc(value: datetime.datetime) -> datetime.datetime:
    """Привести дату из SQLite к UTC без tz — в одном виде с _now()."""
    return value.astimezone(datetime.UTC).replace(tzinfo=None) if value.tzinfo else value


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not durak_game_repository.code_exists(db, code):
            return code


def _seat_of(game: DurakGame, user: User) -> int | None:
    if game.host_id == user.id:
        return 0
    if game.guest_id is not None and game.guest_id == user.id:
        return 1
    return None


def _can_join(game: DurakGame, user: User) -> bool:
    return (
        game.status == DurakGameStatus.WAITING
        and game.guest_id is None
        and game.host_id != user.id
    )


def _lobby_expired(game: DurakGame) -> bool:
    """Лобби, в которое так и не вошёл второй игрок, живёт LOBBY_TTL_MINUTES минут."""
    return (
        game.status == DurakGameStatus.WAITING
        and game.created_at is not None
        and _now() - _naive_utc(game.created_at) > datetime.timedelta(minutes=LOBBY_TTL_MINUTES)
    )


def _expire(db: Session, game: DurakGame) -> DurakGame:
    """Брошенное лобби закрывается само, чтобы не копилось в «Моих партиях»."""
    if _lobby_expired(game):
        game = durak_game_repository.save(
            db, game, status=DurakGameStatus.CANCELLED, ready_deadline=None
        )
        _sync_chat(game)
    return game


def get_for(db: Session, user: User, code: str) -> DurakGame:
    game = durak_game_repository.get_by_code(db, code.upper())
    if game is not None:
        game = _expire(db, game)
    if game is None or (_seat_of(game, user) is None and not _can_join(game, user)):
        raise DurakGameNotFoundError("Партия не найдена или места уже заняты")
    return game


def list_active(db: Session, user: User) -> list[DurakGame]:
    games = [_expire(db, g) for g in durak_game_repository.list_active_for(db, user.id)]
    return [
        g for g in games
        if g.status not in (DurakGameStatus.FINISHED, DurakGameStatus.CANCELLED)
        and _seat_of(g, user) is not None
    ]


def create(db: Session, user: User, vs_bot: bool) -> DurakGame:
    state = durak.new_game()
    if vs_bot:
        durak.run_bot(state)  # бот мог получить первый ход
    return durak_game_repository.create(
        db,
        code=_new_code(db),
        host_id=user.id,
        vs_bot=vs_bot,
        status=DurakGameStatus.PLAYING if vs_bot else DurakGameStatus.WAITING,
        state=state.to_dict(),
    )


def join(db: Session, user: User, code: str) -> DurakGame:
    game = get_for(db, user, code)
    if _seat_of(game, user) is not None:
        return game  # уже в партии — повторное открытие ссылки
    game = durak_game_repository.save(
        db,
        game,
        guest_id=user.id,
        status=DurakGameStatus.READY_CHECK,
        host_ready=False,
        guest_ready=False,
        ready_deadline=None,
    )
    _sync_chat(game)
    push_service.send_to_user(
        db,
        game.host_id,
        title="Соперник нашёлся",
        body=f"{user.full_name} садится играть в дурака — откройте партию и подтвердите участие",
        url=f"/games/durak/{game.code}",
    )
    return game


def ready(db: Session, user: User, code: str) -> DurakGame:
    game = get_for(db, user, code)
    seat = _seat_of(game, user)
    if seat is None:
        raise DurakMoveError("Вы не играете в этой партии")
    if game.status != DurakGameStatus.READY_CHECK:
        return game  # опоздавшее нажатие: партия уже началась или вернулась в ожидание
    flags = {"host_ready": True} if seat == 0 else {"guest_ready": True}
    both = (game.host_ready or seat == 0) and (game.guest_ready or seat == 1)
    if both:
        # Раздаём в момент старта: колода не лежит заранее у создателя.
        flags.update(
            status=DurakGameStatus.PLAYING, state=durak.new_game().to_dict(), ready_deadline=None
        )
    game = durak_game_repository.save(db, game, **flags)
    if both:
        _sync_chat(game)
    return game


def cancel(db: Session, user: User, code: str) -> DurakGame:
    """Закрыть лобби до начала партии. Отменить идущую партию нельзя."""
    game = get_for(db, user, code)
    if _seat_of(game, user) != 0:
        raise DurakMoveError("Закрыть партию может только создатель")
    if game.status == DurakGameStatus.CANCELLED:
        return game
    if game.status not in (DurakGameStatus.WAITING, DurakGameStatus.READY_CHECK):
        raise DurakMoveError("Партия уже началась — закрыть её нельзя")
    game = durak_game_repository.save(
        db, game, status=DurakGameStatus.CANCELLED, ready_deadline=None
    )
    _sync_chat(game)
    return game


def leave(db: Session, user: User, code: str) -> DurakGame:
    """Гость передумал до старта: место снова свободно, создатель ждёт другого."""
    game = get_for(db, user, code)
    if _seat_of(game, user) != 1:
        raise DurakMoveError("Выйти из лобби может только присоединившийся игрок")
    if game.status != DurakGameStatus.READY_CHECK:
        raise DurakMoveError("Выйти можно только до начала партии")
    game = durak_game_repository.save(
        db,
        game,
        status=DurakGameStatus.WAITING,
        guest_id=None,
        host_ready=False,
        guest_ready=False,
        # Лобби снова ищет соперника — 5 минут отсчитываем заново.
        created_at=_now(),
        ready_deadline=None,
    )
    _sync_chat(game)
    return game


def invite_to_chat(db: Session, user: User, code: str) -> DurakGame:
    """Опубликовать приглашение в чате актива (один раз на партию)."""
    game = get_for(db, user, code)
    if _seat_of(game, user) != 0 or game.status != DurakGameStatus.WAITING:
        raise DurakMoveError("Позвать в чат может создатель, пока партия ждёт соперника")
    if not chat_invites_enabled():
        raise DurakMoveError("Чат для приглашений не настроен")
    if game.message_id is not None:
        return game
    caption, buttons = _chat_message(game)
    photo = settings.webapp_url.rstrip("/") + INVITE_IMAGE_PATH
    message_id = telegram_service.send_photo(settings.telegram_games_chat_id, photo, caption, buttons)
    if message_id is None:
        raise DurakMoveError("Не удалось отправить приглашение в чат")
    # Без поднятия версии: на столе ничего не поменялось.
    game.chat_id, game.message_id = settings.telegram_games_chat_id, message_id
    db.commit()
    db.refresh(game)
    return game


def chat_invites_enabled() -> bool:
    return telegram_service.telegram_enabled() and settings.telegram_games_chat_id is not None


def invite_url(game: DurakGame) -> str:
    return telegram_service.startapp_url(f"durak_{game.code}") or (
        settings.webapp_url.rstrip("/") + f"/games/durak/{game.code}"
    )


def _chat_message(game: DurakGame) -> tuple[str, list[dict] | None]:
    """Подпись и кнопки сообщения-приглашения для текущего состояния партии."""
    esc = telegram_service.escape
    host = esc(game.host.full_name)
    guest = esc(game.guest.full_name) if game.guest else None
    head = "🃏 <b>Дурак</b> · подкидной один на один"
    if game.status == DurakGameStatus.WAITING:
        text = f"{head}\n\n<b>{host}</b> ищет соперника.\nПервый, кто нажмёт кнопку, садится за стол."
        return text, [{"text": "Присоединиться", "url": invite_url(game)}]
    if game.status == DurakGameStatus.READY_CHECK:
        return f"{head}\n\n<b>{host}</b> vs <b>{guest}</b>\nПодтверждают участие…", None
    if game.status == DurakGameStatus.PLAYING:
        return f"{head}\n\n<b>{host}</b> vs <b>{guest}</b>\nПартия идёт. Места заняты.", None
    if game.status == DurakGameStatus.CANCELLED:
        return f"{head}\n\n<b>{host}</b> — партия отменена.", None
    state = durak.Game.from_dict(game.state)
    if state.winner is None:
        result = "Ничья!"
    else:
        loser = guest if state.winner == 0 else host
        result = f"<b>{loser}</b> остаётся в дураках."
    return f"{head}\n\n<b>{host}</b> vs <b>{guest}</b>\n{result}", None


def _sync_chat(game: DurakGame) -> None:
    if game.chat_id is None or game.message_id is None:
        return
    caption, buttons = _chat_message(game)
    telegram_service.edit_caption(game.chat_id, game.message_id, caption, buttons)


def move(db: Session, user: User, code: str, payload: DurakMove) -> DurakGame:
    game = get_for(db, user, code)
    seat = _seat_of(game, user)
    if seat is None:
        raise DurakMoveError("Вы не играете в этой партии")
    if game.status != DurakGameStatus.PLAYING:
        raise DurakMoveError("Партия не идёт")
    if payload.version != game.version:
        raise DurakVersionConflictError("Соперник уже сходил — обновляем стол")

    state = durak.Game.from_dict(game.state)
    try:
        if payload.action == "attack":
            durak.attack(state, seat, _require(payload.card))
        elif payload.action == "defend":
            durak.defend(state, seat, _require(payload.target), _require(payload.card))
        elif payload.action == "take":
            durak.take(state, seat)
        elif payload.action == "finish":
            durak.finish_bout(state, seat)
        elif payload.action == "resign":
            durak.resign(state, seat)
        if game.vs_bot:
            durak.run_bot(state)
    except durak.IllegalMove as exc:
        raise DurakMoveError(str(exc)) from exc

    status = DurakGameStatus.FINISHED if state.over else DurakGameStatus.PLAYING
    game = durak_game_repository.save(db, game, state=state.to_dict(), status=status)
    if state.over:
        _sync_chat(game)
    return game


def _require(card: int | None) -> int:
    if card is None:
        raise durak.IllegalMove("Не указана карта")
    return card


def _my_turn(state: durak.Game, seat: int) -> bool:
    """Ждёт ли партия решения этого игрока (для подсветки и списка партий)."""
    if state.over:
        return False
    if seat == state.attacker:
        return not state.table or state.taking or durak.all_covered(state)
    return bool(durak.uncovered(state)) and not state.taking


def is_my_turn(game: DurakGame, user: User) -> bool:
    seat = _seat_of(game, user)
    if seat is None:
        return False
    if game.status == DurakGameStatus.READY_CHECK:
        return not (game.host_ready if seat == 0 else game.guest_ready)
    if game.status != DurakGameStatus.PLAYING:
        return False
    return _my_turn(durak.Game.from_dict(game.state), seat)


def opponent_name(game: DurakGame, user: User) -> str | None:
    if game.vs_bot:
        return BOT_NAME
    other = game.guest if game.host_id == user.id else game.host
    return other.full_name if other else None


def view(game: DurakGame, user: User) -> dict:
    """Партия глазами игрока (или зрителя по приглашению) — под схему DurakOut."""
    state = durak.Game.from_dict(game.state)
    seat = _seat_of(game, user)
    dealt = game.status in (DurakGameStatus.PLAYING, DurakGameStatus.FINISHED)

    def player(idx: int) -> dict | None:
        if idx == 1 and game.vs_bot:
            return {"id": None, "full_name": BOT_NAME, "cards": len(state.hands[1])}
        person = game.host if idx == 0 else game.guest
        if person is None:
            return None
        return {"id": person.id, "full_name": person.full_name, "cards": len(state.hands[idx]) if dealt else 0}

    legal = {"attack": [], "defend": {}, "take": False, "finish": False}
    result = None
    if seat is not None and game.status == DurakGameStatus.PLAYING:
        legal = {
            "attack": durak.legal_attacks(state, seat),
            "defend": {
                str(att): durak.legal_beaters(state, seat, att) for att in durak.uncovered(state)
            } if seat != state.attacker else {},
            "take": durak.can_take(state, seat),
            "finish": durak.can_finish_bout(state, seat),
        }
    if seat is not None and game.status == DurakGameStatus.FINISHED:
        result = "draw" if state.winner is None else ("win" if state.winner == seat else "lose")

    ready = None
    if game.status == DurakGameStatus.READY_CHECK and seat is not None:
        ready = {
            "me": game.host_ready if seat == 0 else game.guest_ready,
            "opponent": game.guest_ready if seat == 0 else game.host_ready,
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
        "hand": durak.sort_hand(state, state.hands[seat]) if seat is not None and dealt else [],
        "table": state.table if dealt else [],
        "trump": state.trump,
        "trump_card": state.trump_card if dealt and state.talon else None,
        "talon": len(state.talon) if dealt else 0,
        "beaten": state.beaten,
        "attacker": state.attacker,
        "taking": state.taking,
        "my_turn": is_my_turn(game, user),
        "legal": legal,
        "result": result,
        "ready": ready,
        "invite_url": invite_url(game) if game.status == DurakGameStatus.WAITING else None,
        "chat_invite": {
            "available": seat == 0 and game.status == DurakGameStatus.WAITING and chat_invites_enabled(),
            "sent": game.message_id is not None,
        },
    }
