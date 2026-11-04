import datetime
import random

import pytest

from app.core.config import settings
from app.games import durak
from app.services import durak_service, telegram_service


def _auth(client, credentials):
    token = client.post("/api/auth/login", data=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _first_legal_move(view):
    """Простейший игрок: защищается, если может, иначе берёт; нападает младшей."""
    legal = view["legal"]
    for target, beaters in legal["defend"].items():
        if beaters:
            return {"action": "defend", "target": int(target), "card": beaters[0]}
    if legal["take"]:
        return {"action": "take"}
    if legal["finish"]:
        return {"action": "finish"}
    if legal["attack"]:
        return {"action": "attack", "card": legal["attack"][0]}
    return None


# ── Механика ──

@pytest.mark.parametrize("seed", range(200))
def test_bot_vs_bot_always_finishes_and_keeps_36_cards(seed):
    game = durak.new_game(seed)
    for _ in range(1000):
        if game.over:
            break
        moved = durak.bot_step(game, game.attacker) or durak.bot_step(game, durak.defender_of(game))
        assert moved, "оба бота ждут друг друга — тупик"
        assert durak.card_count(game) == 36
    assert game.over


def test_beats_rules():
    trump = 0  # пики
    nine_hearts, ten_hearts, six_spades = 1 * 13 + 7, 1 * 13 + 8, 0 * 13 + 4
    assert durak.beats(nine_hearts, ten_hearts, trump)
    assert not durak.beats(ten_hearts, nine_hearts, trump)
    assert durak.beats(ten_hearts, six_spades, trump)  # козырь бьёт некозырь
    assert not durak.beats(six_spades, ten_hearts, trump)


def test_take_lets_attacker_toss_then_finish():
    game = durak.new_game(7)
    att, dfn = game.attacker, durak.defender_of(game)
    durak.attack(game, att, durak.legal_attacks(game, att)[0])
    durak.take(game, dfn)
    assert durak.can_finish_bout(game, att)
    assert durak.legal_beaters(game, dfn, durak.uncovered(game)[0]) == []  # сказал «беру» — не бьёт
    hand_before = len(game.hands[dfn])
    durak.finish_bout(game, att)
    assert len(game.hands[dfn]) == hand_before + 1
    assert game.attacker == att  # взявший пропускает ход


def test_serialization_roundtrip():
    game = durak.new_game(3)
    assert durak.Game.from_dict(game.to_dict()) == game


# ── API ──

def _both_ready(client, code, host, guest):
    first = client.post(f"/api/games/durak/{code}/ready", headers=host).json()
    assert first["status"] == "ready_check" and first["ready"]["me"] is True
    started = client.post(f"/api/games/durak/{code}/ready", headers=guest).json()
    assert started["status"] == "playing" and len(started["hand"]) == 6
    return started


def _later(monkeypatch, seconds):
    future = durak_service._now() + datetime.timedelta(seconds=seconds)
    monkeypatch.setattr(durak_service, "_now", lambda: future)


def _seat_guest(client, host, guest):
    code = client.post("/api/games/durak", json={"vs_bot": False}, headers=host).json()["code"]
    client.post(f"/api/games/durak/{code}/join", json={}, headers=guest)
    return code

def test_game_vs_bot_plays_to_the_end(client, employee_credentials):
    headers = _auth(client, employee_credentials)
    view = client.post("/api/games/durak", json={"vs_bot": True}, headers=headers).json()
    assert view["status"] == "playing" and view["opponent"]["full_name"] == "Бот"
    assert len(view["hand"]) + view["opponent"]["cards"] + view["talon"] + len(view["table"]) >= 12

    for _ in range(500):
        if view["status"] == "finished":
            break
        move = _first_legal_move(view)
        assert move is not None, "игроку нечем ходить, а партия идёт"
        response = client.post(
            f"/api/games/durak/{view['code']}/move", json={**move, "version": view["version"]}, headers=headers
        )
        assert response.status_code == 200, response.json()
        view = response.json()
    assert view["status"] == "finished"
    assert view["result"] in ("win", "lose", "draw")


def test_invite_join_and_privacy(client, employee_credentials, manager_credentials, admin_credentials):
    host, guest, other = (_auth(client, c) for c in (employee_credentials, manager_credentials, admin_credentials))
    created = client.post("/api/games/durak", json={"vs_bot": False}, headers=host).json()
    code = created["code"]
    assert created["status"] == "waiting" and created["hand"] == []

    # По ссылке видно приглашение, карт ещё нет.
    preview = client.get(f"/api/games/durak/{code.lower()}", headers=guest).json()
    assert preview["can_join"] and preview["seat"] is None and preview["opponent"]["full_name"] == "Олег Сотрудник"

    joined = client.post(f"/api/games/durak/{code}/join", json={}, headers=guest).json()
    assert joined["status"] == "ready_check" and joined["seat"] == 1 and joined["hand"] == []
    assert joined["ready"] == {"me": False, "opponent": False}

    # Место занято сразу, ещё до подтверждения: третьему партия не видна.
    assert client.get(f"/api/games/durak/{code}", headers=other).status_code == 404
    assert client.post(f"/api/games/durak/{code}/join", json={}, headers=other).status_code == 404

    _both_ready(client, code, host, guest)

    # Ходит тот, у кого младший козырь; второй получает 400, устаревшая версия — 409.
    host_view = client.get(f"/api/games/durak/{code}", headers=host).json()
    mover, waiter = (host, guest) if host_view["attacker"] == 0 else (guest, host)
    mover_view = client.get(f"/api/games/durak/{code}", headers=mover).json()
    card = mover_view["legal"]["attack"][0]
    bad = client.post(
        f"/api/games/durak/{code}/move",
        json={"action": "attack", "card": card, "version": mover_view["version"]},
        headers=waiter,
    )
    assert bad.status_code == 400
    ok = client.post(
        f"/api/games/durak/{code}/move",
        json={"action": "attack", "card": card, "version": mover_view["version"]},
        headers=mover,
    )
    assert ok.status_code == 200
    stale = client.post(
        f"/api/games/durak/{code}/move",
        json={"action": "take", "version": mover_view["version"]},
        headers=waiter,
    )
    assert stale.status_code == 409

    # Оба видят партию в списке, у защитника — его ход.
    waiter_list = client.get("/api/games/durak", headers=waiter).json()
    assert [g["code"] for g in waiter_list] == [code] and waiter_list[0]["my_turn"]


def test_resign_finishes_game(client, employee_credentials):
    headers = _auth(client, employee_credentials)
    view = client.post("/api/games/durak", json={"vs_bot": True}, headers=headers).json()
    done = client.post(
        f"/api/games/durak/{view['code']}/move", json={"action": "resign", "version": view["version"]}, headers=headers
    ).json()
    assert done["status"] == "finished" and done["result"] == "lose"
    assert client.get("/api/games/durak", headers=headers).json() == []


def test_hidden_cards_not_leaked(client, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = client.post("/api/games/durak", json={"vs_bot": False}, headers=host).json()["code"]
    client.post(f"/api/games/durak/{code}/join", json={}, headers=guest)
    _both_ready(client, code, host, guest)
    host_view = client.get(f"/api/games/durak/{code}", headers=host).json()
    guest_view = client.get(f"/api/games/durak/{code}", headers=guest).json()
    assert len(host_view["hand"]) == 6 and len(guest_view["hand"]) == 6
    assert not set(host_view["hand"]) & set(guest_view["hand"])
    assert "hands" not in host_view and "talon_cards" not in host_view
    random.seed(0)


def test_lobby_expires_after_five_minutes(client, monkeypatch, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = client.post("/api/games/durak", json={"vs_bot": False}, headers=host).json()["code"]

    # До пяти минут лобби живо: гость ещё может зайти.
    _later(monkeypatch, durak_service.LOBBY_TTL_MINUTES * 60 - 30)
    assert client.get(f"/api/games/durak/{code}", headers=host).json()["status"] == "waiting"
    assert client.get(f"/api/games/durak/{code}", headers=guest).json()["can_join"] is True

    # После пяти минут комната закрыта: из списка пропала, по ссылке не войти.
    _later(monkeypatch, 60)
    assert client.get(f"/api/games/durak/{code}", headers=host).json()["status"] == "cancelled"
    assert client.get("/api/games/durak", headers=host).json() == []
    assert client.get(f"/api/games/durak/{code}", headers=guest).status_code == 404
    assert client.post(f"/api/games/durak/{code}/join", json={}, headers=guest).status_code == 404


def test_guest_join_stops_lobby_timer(client, monkeypatch, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = _seat_guest(client, host, guest)

    # Второй успел зайти до истечения пяти минут — дальше таймер лобби не действует.
    _later(monkeypatch, durak_service.LOBBY_TTL_MINUTES * 60 + 3600)
    view = client.get(f"/api/games/durak/{code}", headers=host).json()
    assert view["status"] == "ready_check" and view["opponent"]["full_name"] == "Маша Менеджер"


def test_ready_check_waits_without_timer(client, monkeypatch, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = _seat_guest(client, host, guest)

    first = client.post(f"/api/games/durak/{code}/ready", headers=host).json()
    assert first["status"] == "ready_check" and first["ready"]["me"] is True

    # Пауза в сутки ничего не отменяет: подтверждение одного игрока сохранено.
    _later(monkeypatch, 24 * 3600)
    still = client.get(f"/api/games/durak/{code}", headers=host).json()
    assert still["status"] == "ready_check"
    assert still["ready"] == {"me": True, "opponent": False}

    # Второй нажал «Готов» после паузы — партия стартует.
    started = client.post(f"/api/games/durak/{code}/ready", headers=guest).json()
    assert started["status"] == "playing" and len(started["hand"]) == 6


def test_host_cancels_ready_check_lobby(client, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = _seat_guest(client, host, guest)
    client.post(f"/api/games/durak/{code}/ready", headers=host)

    # Создатель передумал: лобби закрывается и после прихода гостя.
    cancelled = client.post(f"/api/games/durak/{code}/cancel", headers=host).json()
    assert cancelled["status"] == "cancelled"
    assert client.get("/api/games/durak", headers=host).json() == []
    assert client.get(f"/api/games/durak/{code}", headers=guest).json()["status"] == "cancelled"


def test_guest_leaves_ready_check_seat_reopens(client, employee_credentials, manager_credentials, admin_credentials):
    host, guest, other = (_auth(client, c) for c in (employee_credentials, manager_credentials, admin_credentials))
    code = _seat_guest(client, host, guest)
    client.post(f"/api/games/durak/{code}/ready", headers=host)

    # Выйти может только гость — создатель закрывает лобби целиком.
    assert client.post(f"/api/games/durak/{code}/leave", headers=host).status_code == 400

    left = client.post(f"/api/games/durak/{code}/leave", headers=guest).json()
    assert left["status"] == "waiting" and left["seat"] is None

    # Место снова свободно, готовность создателя сброшена.
    host_view = client.get(f"/api/games/durak/{code}", headers=host).json()
    assert host_view["status"] == "waiting" and host_view["opponent"] is None
    assert host_view["ready"] is None
    assert client.get(f"/api/games/durak/{code}", headers=guest).json()["can_join"] is True

    joined = client.post(f"/api/games/durak/{code}/join", json={}, headers=other).json()
    assert joined["status"] == "ready_check" and joined["seat"] == 1


def test_lobby_timer_restarts_after_guest_leaves(client, monkeypatch, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = _seat_guest(client, host, guest)

    # Лобби существует дольше пяти минут, но гость ушёл — окно ожидания новое.
    _later(monkeypatch, 3600)
    client.post(f"/api/games/durak/{code}/leave", headers=guest)
    assert client.get(f"/api/games/durak/{code}", headers=host).json()["status"] == "waiting"

    _later(monkeypatch, durak_service.LOBBY_TTL_MINUTES * 60 + 1)
    assert client.get(f"/api/games/durak/{code}", headers=host).json()["status"] == "cancelled"


def test_host_cancels_waiting_game(client, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = client.post("/api/games/durak", json={"vs_bot": False}, headers=host).json()["code"]

    # Закрыть лобби может только создатель.
    assert client.post(f"/api/games/durak/{code}/cancel", headers=guest).status_code == 400

    cancelled = client.post(f"/api/games/durak/{code}/cancel", headers=host).json()
    assert cancelled["status"] == "cancelled"
    assert client.get("/api/games/durak", headers=host).json() == []
    # Повторная отмена — без ошибки, партия уже закрыта.
    assert client.post(f"/api/games/durak/{code}/cancel", headers=host).json()["status"] == "cancelled"


def test_cannot_cancel_started_game(client, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = _seat_guest(client, host, guest)
    _both_ready(client, code, host, guest)
    response = client.post(f"/api/games/durak/{code}/cancel", headers=host)
    assert response.status_code == 400


def test_stale_waiting_game_expires(client, monkeypatch, employee_credentials):
    host = _auth(client, employee_credentials)
    code = client.post("/api/games/durak", json={"vs_bot": False}, headers=host).json()["code"]

    _later(monkeypatch, durak_service.LOBBY_TTL_MINUTES * 60 + 60)
    assert client.get(f"/api/games/durak/{code}", headers=host).json()["status"] == "cancelled"
    assert client.get("/api/games/durak", headers=host).json() == []


def test_moves_blocked_until_both_ready(client, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = _seat_guest(client, host, guest)
    view = client.get(f"/api/games/durak/{code}", headers=host).json()
    response = client.post(
        f"/api/games/durak/{code}/move", json={"action": "take", "version": view["version"]}, headers=host
    )
    assert response.status_code == 400


def test_chat_invite_message_follows_game(client, monkeypatch, employee_credentials, manager_credentials):
    sent, edits = [], []
    monkeypatch.setattr(settings, "telegram_games_chat_id", -100500)
    monkeypatch.setattr(telegram_service, "telegram_enabled", lambda: True)
    monkeypatch.setattr(telegram_service, "startapp_url", lambda p: f"https://t.me/ik_bot?startapp={p}")
    monkeypatch.setattr(
        telegram_service, "send_photo",
        lambda chat_id, photo, caption, buttons: sent.append((chat_id, caption, buttons)) or 77,
    )
    monkeypatch.setattr(
        telegram_service, "edit_caption",
        lambda chat_id, message_id, caption, buttons: edits.append((message_id, caption, buttons)),
    )
    monkeypatch.setattr("app.services.push_service.send_to_user", lambda *a, **k: None)
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    created = client.post("/api/games/durak", json={"vs_bot": False}, headers=host).json()
    code = created["code"]
    assert created["chat_invite"] == {"available": True, "sent": False}
    assert created["invite_url"] == f"https://t.me/ik_bot?startapp=durak_{code}"

    # Позвать в чат может только создатель.
    assert client.post(f"/api/games/durak/{code}/invite-chat", headers=guest).status_code == 400
    invited = client.post(f"/api/games/durak/{code}/invite-chat", headers=host).json()
    assert invited["chat_invite"]["sent"] is True
    chat_id, caption, buttons = sent[0]
    assert chat_id == -100500 and "Олег Сотрудник" in caption and "ищет соперника" in caption
    assert buttons[0]["url"] == f"https://t.me/ik_bot?startapp=durak_{code}"
    # Повторное нажатие не плодит сообщения.
    client.post(f"/api/games/durak/{code}/invite-chat", headers=host)
    assert len(sent) == 1

    client.post(f"/api/games/durak/{code}/join", json={}, headers=guest)
    message_id, caption, buttons = edits[-1]
    assert message_id == 77 and "Маша Менеджер" in caption and buttons is None  # кнопки больше нет

    started = _both_ready(client, code, host, guest)
    assert "Партия идёт" in edits[-1][1]

    seat_view = client.get(f"/api/games/durak/{code}", headers=guest).json()
    client.post(
        f"/api/games/durak/{code}/move", json={"action": "resign", "version": seat_view["version"]}, headers=guest
    )
    assert "Маша Менеджер</b> остаётся в дураках" in edits[-1][1]
