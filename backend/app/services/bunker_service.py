"""Партии в «Бункер»: лобби, старт, ходы игроков и «Дальше» от создателя.

Механика — app/games/bunker.py. Обсуждают вживую, приложение ведёт карты,
фазы и голосования. WAITING (лобби: заходят по ссылке, выйти можно) →
создатель жмёт «Начать» (от MIN_PLAYERS) → PLAYING → FINISHED. Создатель может
распустить лобби или остановить партию — CANCELLED.

Столы для очной игры заводит админ (create_table): состав по Telegram-тегам;
пока карты не розданы, к столу можно и присоединиться сам (ссылкой или из
списка открытых столов в «Играх»). Ведущий стола может не играть — тогда он наблюдатель:
видит все карты и ведёт фазы, своего персонажа у него нет.

Видимость: партию видят её игроки и ведущий; чужую — только лобби (или стол
до раздачи), где есть место. Закрытые карты отдаём только их владельцу (и ведущему-наблюдателю).
После старта место игрока — его индекс в state["user_ids"].
"""
import re
import copy
import datetime
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.games import bunker
from app.models.bunker_game import BunkerGame, BunkerStatus
from app.models.user import User, UserRole
from app.repositories import bunker_game_repository, user_repository
from app.schemas.bunker import BunkerMove
from app.services import push_service, telegram_service
from app.services.exceptions import BunkerMoveError, BunkerNotFoundError, BunkerVersionConflictError

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
INVITE_IMAGE_PATH = "/og/bunker-invite.png"
START_PREFIX = "bunker_"


def _now() -> datetime.datetime:
    """UTC без tz — в таком виде SQLite отдаёт phase_started_at обратно."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not bunker_game_repository.code_exists(db, code):
            return code


def _user_ids(game: BunkerGame) -> list[int]:
    if game.state is not None:
        return game.state["user_ids"]
    return [p.user_id for p in game.players]


def _seat_of(game: BunkerGame, user: User) -> int | None:
    ids = _user_ids(game)
    return ids.index(user.id) if user.id in ids else None


def _is_observer(game: BunkerGame, user: User) -> bool:
    """Ведущий, который сам не играет."""
    return game.host_id == user.id and _seat_of(game, user) is None


def _can_join(game: BunkerGame, user: User) -> bool:
    return (
        game.status == BunkerStatus.WAITING
        and len(game.players) < bunker.MAX_PLAYERS
        and _seat_of(game, user) is None
    )


def get_for(db: Session, user: User, code: str) -> BunkerGame:
    game = bunker_game_repository.get_by_code(db, code.upper())
    if game is None or (
        _seat_of(game, user) is None and game.host_id != user.id and not _can_join(game, user)
    ):
        raise BunkerNotFoundError("Партия не найдена или уже началась")
    return game


def list_active(db: Session, user: User) -> list[BunkerGame]:
    return bunker_game_repository.list_active_for(db, user.id)


def create(db: Session, user: User) -> BunkerGame:
    return bunker_game_repository.create(db, code=_new_code(db), host_id=user.id, player_ids=[user.id])


# ── Столы для очной игры (админка) ──

def parse_tags(raw: list[str]) -> list[str]:
    """Теги из списка строк: «@tag», «tag», через запятую, пробел или с новой строки."""
    seen, tags = set(), []
    for chunk in raw:
        for tag in re.split(r"[\s,;]+", chunk):
            tag = tag.strip().lstrip("@")
            if tag and tag.lower() not in seen:
                seen.add(tag.lower())
                tags.append(tag)
    return tags


def _resolve(db: Session, tags: list[str], host_tag: str | None, admin: User) -> tuple[list[int], int, list[str]]:
    """Теги → id игроков, id ведущего и не найденные теги."""
    host_tags = parse_tags([host_tag]) if host_tag else []
    found = user_repository.find_by_telegram_tags(db, tags + host_tags)
    missing = [t for t in tags + host_tags if t.lower() not in found]
    player_ids = [found[t.lower()].id for t in tags if t.lower() in found]
    host_id = found[host_tags[0].lower()].id if host_tags and host_tags[0].lower() in found else admin.id
    if len(player_ids) > bunker.MAX_PLAYERS:
        raise BunkerMoveError(f"За столом не больше {bunker.MAX_PLAYERS} игроков")
    return player_ids, host_id, missing


def create_table(
    db: Session, admin: User, title: str, tags: list[str], host_tag: str | None
) -> tuple[BunkerGame, list[str]]:
    player_ids, host_id, missing = _resolve(db, parse_tags(tags), host_tag, admin)
    game = bunker_game_repository.create(
        db, code=_new_code(db), host_id=host_id, player_ids=player_ids, title=title.strip()
    )
    # Сам себя ведущим админ не уведомляет — иначе на каждый пустой стол по сообщению.
    _notify_seated(db, game, player_ids + ([host_id] if host_id != admin.id else []))
    return game, missing


def update_table(
    db: Session, admin: User, code: str, title: str, tags: list[str], host_tag: str | None
) -> tuple[BunkerGame, list[str]]:
    game = _get_table(db, code)
    if game.status != BunkerStatus.WAITING:
        raise BunkerMoveError("Карты уже розданы — состав не поменять")
    player_ids, host_id, missing = _resolve(db, parse_tags(tags), host_tag, admin)
    # Сели сами, а Telegram-тега нет (вход из браузера) — в списке тегов их не
    # перечислить, поэтому не выкидываем.
    untagged = [p.user_id for p in game.players if not p.user.telegram_username and p.user_id not in player_ids]
    player_ids += untagged
    if len(player_ids) > bunker.MAX_PLAYERS:
        raise BunkerMoveError(f"За столом не больше {bunker.MAX_PLAYERS} игроков")
    before = set(_user_ids(game)) | {game.host_id}
    game = bunker_game_repository.set_players(db, game, player_ids, title=title.strip(), host_id=host_id)
    _notify_seated(db, game, [uid for uid in player_ids + [host_id] if uid not in before])
    return game, missing


def list_tables(db: Session) -> list[BunkerGame]:
    return bunker_game_repository.list_tables(db)


def list_open_tables(db: Session, user: User) -> list[BunkerGame]:
    """Столы, за которые можно сесть: карты не розданы, есть место, меня там нет."""
    tables = [
        g for g in bunker_game_repository.list_tables(db)
        if _can_join(g, user) and g.host_id != user.id
    ]
    # Как столы заводили: «Стол 1», «Стол 2»… — сверху вниз.
    return sorted(tables, key=lambda g: g.id)


def _get_table(db: Session, code: str) -> BunkerGame:
    game = bunker_game_repository.get_by_code(db, code.upper())
    if game is None or not game.is_table:
        raise BunkerNotFoundError("Стол не найден")
    return game


def start_table(db: Session, admin: User, code: str) -> BunkerGame:
    return _start(db, _get_table(db, code), admin)


def cancel_table(db: Session, admin: User, code: str) -> BunkerGame:
    game = _get_table(db, code)
    if game.status in (BunkerStatus.WAITING, BunkerStatus.PLAYING):
        game = bunker_game_repository.save(db, game, status=BunkerStatus.CANCELLED)
    return game


def _notify_seated(db: Session, game: BunkerGame, user_ids: list[int]) -> None:
    ids = list(dict.fromkeys(user_ids))
    hosts = [uid for uid in ids if uid == game.host_id and uid not in _user_ids(game)]
    players = [uid for uid in ids if uid not in hosts]
    url = f"/games/bunker/{game.code}"
    if players:
        push_service.send_to_users(
            db, players, title=f"Бункер · {game.title}",
            body="Вас посадили за стол. Откройте игру — карты раздадут, когда все соберутся.", url=url,
        )
    if hosts:
        push_service.send_to_users(
            db, hosts, title=f"Бункер · {game.title}",
            body="Вы ведёте этот стол. Когда все на месте — раздайте карты.", url=url,
        )


def join(db: Session, user: User, code: str) -> BunkerGame:
    game = get_for(db, user, code)
    if _seat_of(game, user) is not None:
        return game
    game = bunker_game_repository.add_player(db, game, user.id)
    _sync_chat(game)
    return game


def leave(db: Session, user: User, code: str) -> BunkerGame:
    """Выйти из лобби. Создатель не выходит, а распускает лобби (stop)."""
    game = get_for(db, user, code)
    if game.status != BunkerStatus.WAITING:
        raise BunkerMoveError("Партия уже идёт — выйти нельзя")
    if game.host_id == user.id:
        raise BunkerMoveError("Создатель не может выйти — можно только распустить лобби")
    if _seat_of(game, user) is not None:
        game = bunker_game_repository.remove_player(db, game, user.id)
        _sync_chat(game)
    return game


def start(db: Session, user: User, code: str) -> BunkerGame:
    game = get_for(db, user, code)
    if game.host_id != user.id:
        raise BunkerMoveError("Начать партию может только ведущий")
    return _start(db, game, user)


def _start(db: Session, game: BunkerGame, user: User) -> BunkerGame:
    if game.status != BunkerStatus.WAITING:
        return game
    try:
        state = bunker.new_game(len(game.players))
    except bunker.IllegalMove as exc:
        raise BunkerMoveError(str(exc)) from exc
    state["user_ids"] = [p.user_id for p in game.players]
    game = bunker_game_repository.save(
        db, game, status=BunkerStatus.PLAYING, state=state, phase_started_at=_now()
    )
    _sync_chat(game)
    push_service.send_to_users(
        db,
        [uid for uid in state["user_ids"] if uid != user.id],
        title="Бункер начался",
        body=f"{state['catastrophe']['title']}. Мест в бункере: {state['seats']}. Откройте свою карту.",
        url=f"/games/bunker/{game.code}",
    )
    return game


def move(db: Session, user: User, code: str, payload: BunkerMove) -> BunkerGame:
    game = get_for(db, user, code)
    seat = _seat_of(game, user)
    is_host = game.host_id == user.id
    if seat is None and not is_host:
        raise BunkerMoveError("Вы не играете в этой партии")

    if payload.action == "stop":
        if not is_host:
            raise BunkerMoveError("Остановить партию может только создатель")
        if game.status not in (BunkerStatus.WAITING, BunkerStatus.PLAYING):
            return game
        game = bunker_game_repository.save(db, game, status=BunkerStatus.CANCELLED)
        _sync_chat(game)
        return game

    if game.status != BunkerStatus.PLAYING:
        raise BunkerMoveError("Партия не идёт")
    if payload.action == "advance":
        if not is_host:
            raise BunkerMoveError("Ведёт партию создатель")
        # Двойное нажатие или устаревший экран не должны перепрыгнуть фазу.
        if payload.version != game.version:
            raise BunkerVersionConflictError("Партия уже ушла дальше — обновляем")

    # Копия целиком: правка вложенных списков на месте не видна SQLAlchemy.
    state = copy.deepcopy(game.state)
    phase = state["phase"]
    if seat is None and payload.action in ("reveal", "vote"):
        raise BunkerMoveError("Вы ведёте стол, а не играете")
    try:
        if payload.action == "reveal":
            if payload.category is None:
                raise bunker.IllegalMove("Не выбрана карта")
            bunker.reveal(state, seat, payload.category)
        elif payload.action == "vote":
            if payload.target is None:
                raise bunker.IllegalMove("Не выбран игрок")
            bunker.vote(state, seat, payload.target)
        else:
            bunker.advance(state)
    except bunker.IllegalMove as exc:
        raise BunkerMoveError(str(exc)) from exc

    fields = {"state": state}
    if state["phase"] != phase:
        fields["phase_started_at"] = _now()
    if bunker.over(state):
        fields["status"] = BunkerStatus.FINISHED
    game = bunker_game_repository.save(db, game, **fields)
    if bunker.over(state):
        _sync_chat(game)
    return game


def invite_to_chat(db: Session, user: User, code: str) -> BunkerGame:
    """Опубликовать приглашение в чате актива (один раз на партию)."""
    game = get_for(db, user, code)
    if game.host_id != user.id or game.status != BunkerStatus.WAITING:
        raise BunkerMoveError("Позвать в чат может создатель, пока собирается лобби")
    if not chat_invites_enabled():
        raise BunkerMoveError("Чат для приглашений не настроен")
    if game.message_id is not None:
        return game
    caption, buttons = _chat_message(game)
    photo = settings.webapp_url.rstrip("/") + INVITE_IMAGE_PATH
    message_id = telegram_service.send_photo(settings.telegram_games_chat_id, photo, caption, buttons)
    if message_id is None:
        raise BunkerMoveError("Не удалось отправить приглашение в чат")
    game.chat_id, game.message_id = settings.telegram_games_chat_id, message_id
    db.commit()
    db.refresh(game)
    return game


def chat_invites_enabled() -> bool:
    return telegram_service.telegram_enabled() and settings.telegram_games_chat_id is not None


def invite_url(game: BunkerGame) -> str:
    return telegram_service.startapp_url(f"{START_PREFIX}{game.code}") or (
        settings.webapp_url.rstrip("/") + f"/games/bunker/{game.code}"
    )


def _chat_message(game: BunkerGame) -> tuple[str, list[dict] | None]:
    esc = telegram_service.escape
    host = esc(game.host.full_name)
    head = "☢️ <b>Бункер</b> · кого пустим в убежище?"
    count = len(_user_ids(game))
    if game.status == BunkerStatus.WAITING:
        text = (
            f"{head}\n\n<b>{host}</b> собирает выживших: {count} из {bunker.MAX_PLAYERS}.\n"
            f"Нужно минимум {bunker.MIN_PLAYERS}. Обсуждаем вживую, карты и голосование — в трекере."
        )
        return text, [{"text": "Присоединиться", "url": invite_url(game)}]
    if game.status == BunkerStatus.PLAYING:
        title = esc(game.state["catastrophe"]["title"])
        return f"{head}\n\n{title}. Игроков: {count}, мест: {game.state['seats']}.\nИдёт игра, вход закрыт.", None
    if game.status == BunkerStatus.CANCELLED:
        return f"{head}\n\nПартия отменена.", None
    names = {p.user_id: p.user.full_name for p in game.players}
    saved = [esc(names.get(game.state["user_ids"][i], "?")) for i in bunker.active(game.state)]
    return f"{head}\n\nВ бункер попали: <b>{', '.join(saved)}</b>.", None


def _sync_chat(game: BunkerGame) -> None:
    if game.chat_id is None or game.message_id is None:
        return
    caption, buttons = _chat_message(game)
    telegram_service.edit_caption(game.chat_id, game.message_id, caption, buttons)


def is_my_turn(game: BunkerGame, user: User) -> bool:
    """Ждут ли от игрока действия: открыть карту, проголосовать или (создатель) вести."""
    seat = _seat_of(game, user)
    if seat is None and game.host_id != user.id:
        return False
    if game.status == BunkerStatus.WAITING:
        return game.host_id == user.id and len(game.players) >= bunker.MIN_PLAYERS
    if game.status != BunkerStatus.PLAYING:
        return False
    state = game.state
    active = seat is not None and seat in bunker.active(state)
    if state["phase"] == "reveal":
        return active and seat not in state["revealed_round"]
    if state["phase"] == "vote":
        return active and str(seat) not in state["votes"]
    return game.host_id == user.id


def view(game: BunkerGame, user: User) -> dict:
    """Партия глазами игрока (или приглашённого) — под схему BunkerOut."""
    seat = _seat_of(game, user)
    observer = _is_observer(game, user)
    state = game.state
    names = {p.user_id: p.user.full_name for p in game.players}

    players = []
    for idx, uid in enumerate(_user_ids(game)):
        item = {
            "seat": idx,
            "id": uid,
            "full_name": names.get(uid, "Игрок"),
            "is_host": uid == game.host_id,
            "out": False,
            "out_round": None,
            "cards": {},
            "hidden": [],
            "revealed_now": False,
            "voted": False,
        }
        if state is not None:
            p = state["players"][idx]
            own = idx == seat or observer
            item.update(
                out=p["out"],
                out_round=p["out_round"],
                cards={c: v for c, v in p["cards"].items() if own or c in p["revealed"]},
                hidden=[c for c in bunker.CATEGORIES if c not in p["revealed"]] if own else [],
                # Ведущему-наблюдателю видны все карты: закрытые помечены в hidden.
                revealed_now=idx in state["revealed_round"],
                voted=str(idx) in state["votes"],
            )
        players.append(item)

    phase_seconds = 0.0
    if game.phase_started_at is not None and game.status == BunkerStatus.PLAYING:
        phase_seconds = max(0.0, (_now() - game.phase_started_at).total_seconds())

    waiting = game.status == BunkerStatus.WAITING
    return {
        "code": game.code,
        "status": game.status,
        "version": game.version,
        "seat": seat,
        "is_host": game.host_id == user.id,
        "observer": observer,
        "title": game.title,
        "can_join": _can_join(game, user),
        "min_players": bunker.MIN_PLAYERS,
        "max_players": bunker.MAX_PLAYERS,
        "players": players,
        "catastrophe": state["catastrophe"] if state else None,
        "bunker": state["bunker"] if state else None,
        "seats": state["seats"] if state else None,
        "round": state["round"] if state else None,
        "rounds": bunker.ROUNDS,
        "phase": state["phase"] if state else None,
        "phase_seconds": phase_seconds,
        "to_exclude": bunker.to_exclude(state) if state else 0,
        "candidates": state["candidates"] if state else None,
        "my_vote": state["votes"].get(str(seat)) if state and seat is not None else None,
        "last_vote": state["last_vote"] if state else None,
        "invite_url": invite_url(game) if waiting else None,
        "chat_invite": {
            "available": game.host_id == user.id and waiting and chat_invites_enabled(),
            "sent": game.message_id is not None,
        },
    }


def table_view(game: BunkerGame) -> dict:
    """Стол в админке — под схему BunkerTableOut."""
    names = {p.user_id: p.user for p in game.players}
    state = game.state
    return {
        "code": game.code,
        "title": game.title,
        "status": game.status,
        "host": {"id": game.host.id, "full_name": game.host.full_name, "tag": game.host.telegram_username},
        "host_plays": game.host_id in _user_ids(game),
        "players": [
            {
                "id": uid,
                "full_name": names[uid].full_name if uid in names else "Игрок",
                "tag": names[uid].telegram_username if uid in names else None,
                "out": bool(state and state["players"][idx]["out"]),
            }
            for idx, uid in enumerate(_user_ids(game))
        ],
        "round": state["round"] if state else None,
        "phase": state["phase"] if state else None,
    }
