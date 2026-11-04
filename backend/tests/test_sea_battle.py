import datetime
import random

import pytest

from app.core.config import settings
from app.games import seabattle
from app.services import sea_battle_service, telegram_service


def _auth(client, credentials):
    token = client.post("/api/auth/login", data=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _move(client, headers, view, **payload):
    return client.post(
        f"/api/games/sea/{view['code']}/move", json={**payload, "version": view["version"]}, headers=headers
    )


def _free_cell(view):
    shots = view["enemy_board"]["shots"]
    return next(c for c in range(100) if str(c) not in shots)


# ── Механика ──

@pytest.mark.parametrize("seed", range(50))
def test_random_fleet_is_valid(seed):
    fleet = seabattle.random_fleet(random.Random(seed))
    assert seabattle.validate_fleet(fleet) == fleet


@pytest.mark.parametrize(
    "ships",
    [
        [[0, 1, 2, 3]],  # неполный флот
        [[0, 1, 2, 3], [20, 21, 22], [40, 41, 42], [60, 61], [64, 65], [68, 69], [80], [82], [84], [4]],  # [4] касается
        [[0, 1, 2, 4], [20, 21, 22], [40, 41, 42], [60, 61], [64, 65], [68, 69], [80], [82], [84], [86]],  # с дыркой
        [[8, 9, 10, 11], [20, 21, 22], [40, 41, 42], [60, 61], [64, 65], [68, 69], [80], [82], [84], [86]],  # через край
    ],
)
def test_invalid_fleets_rejected(ships):
    with pytest.raises(seabattle.IllegalMove):
        seabattle.validate_fleet(ships)


@pytest.mark.parametrize("seed", range(30))
def test_bot_vs_bot_finishes(seed):
    rng = random.Random(seed)
    game = seabattle.new_game(rng)
    for seat in (0, 1):
        seabattle.place_fleet(game, seat, seabattle.random_fleet(rng))
    for _ in range(200):
        if game.over:
            break
        seabattle.fire(game, game.turn, seabattle.bot_target(game.boards[1 - game.turn], rng))
    assert game.over and game.boards[1 - game.winner].all_sunk()


def test_hit_keeps_turn_and_sunk_is_outlined():
    game = seabattle.Game(turn=0)
    game.boards[1].ships = [[0, 1]]
    assert seabattle.fire(game, 0, 0) == "hit" and game.turn == 0
    assert seabattle.fire(game, 0, 1) == "sunk"
    assert game.boards[1].shots[10] == "miss" and game.boards[1].shots[2] == "miss"
    assert game.over and game.winner == 0
    with pytest.raises(seabattle.IllegalMove):
        seabattle.fire(game, 0, 5)


def test_miss_passes_turn_and_repeat_rejected():
    game = seabattle.Game(turn=0)
    game.boards[1].ships = [[0]]
    assert seabattle.fire(game, 0, 50) == "miss" and game.turn == 1
    with pytest.raises(seabattle.IllegalMove):
        seabattle.fire(game, 0, 51)  # не его ход
    game.turn = 0
    with pytest.raises(seabattle.IllegalMove):
        seabattle.fire(game, 0, 50)


def test_bot_finishes_wounded_ship():
    board = seabattle.Board(ships=[[44, 45, 46]], shots={44: "hit", 45: "hit"})
    for _ in range(20):
        assert seabattle.bot_target(board) in (43, 46)


def test_serialization_roundtrip():
    game = seabattle.new_game(random.Random(1))
    game.boards[0].ships = seabattle.random_fleet(random.Random(2))
    game.boards[0].shots = {3: "miss", 4: "hit"}
    assert seabattle.Game.from_dict(game.to_dict()) == game


# ── API ──

def test_game_vs_bot_plays_to_the_end(client, employee_credentials):
    headers = _auth(client, employee_credentials)
    view = client.post("/api/games/sea", json={"vs_bot": True}, headers=headers).json()
    assert view["status"] == "placing" and view["opponent"]["full_name"] == "Бот"
    assert view["enemy_board"]["ships"] == []  # флот бота не виден

    # Выстрел до расстановки не проходит, кривой флот — тоже.
    assert _move(client, headers, view, action="fire", cell=0).status_code == 400
    assert _move(client, headers, view, action="place", ships=[[0, 1, 2, 3]]).status_code == 400

    fleet = seabattle.random_fleet(random.Random(5))
    view = _move(client, headers, view, action="place", ships=fleet).json()
    assert view["status"] == "playing" and view["my_turn"] and view["my_board"]["ships"] == fleet

    for _ in range(200):
        if view["status"] == "finished":
            break
        response = _move(client, headers, view, action="fire", cell=_free_cell(view))
        assert response.status_code == 200, response.json()
        view = response.json()
    assert view["status"] == "finished" and view["result"] in ("win", "lose")
    assert len(view["enemy_board"]["ships"]) == 10  # в конце флот соперника открыт


def test_human_game_flow_and_privacy(client, employee_credentials, manager_credentials, admin_credentials):
    host, guest, other = (_auth(client, c) for c in (employee_credentials, manager_credentials, admin_credentials))
    code = client.post("/api/games/sea", json={"vs_bot": False}, headers=host).json()["code"]
    assert client.get(f"/api/games/sea/{code}", headers=guest).json()["can_join"]
    joined = client.post(f"/api/games/sea/{code}/join", json={}, headers=guest).json()
    assert joined["status"] == "ready_check"
    assert client.get(f"/api/games/sea/{code}", headers=other).status_code == 404

    client.post(f"/api/games/sea/{code}/ready", headers=host)
    started = client.post(f"/api/games/sea/{code}/ready", headers=guest).json()
    assert started["status"] == "placing" and started["my_turn"]

    host_fleet, guest_fleet = seabattle.random_fleet(random.Random(1)), seabattle.random_fleet(random.Random(2))
    host_view = client.get(f"/api/games/sea/{code}", headers=host).json()
    host_view = _move(client, host, host_view, action="place", ships=host_fleet).json()
    assert host_view["status"] == "placing" and host_view["opponent"]["placed"] is False

    guest_view = client.get(f"/api/games/sea/{code}", headers=guest).json()
    assert guest_view["opponent"]["placed"] is True
    assert guest_view["enemy_board"]["ships"] == []  # чужой флот не утекает
    # Гость расставлял по версии до хоста — расстановка всё равно принимается.
    guest_view = _move(client, guest, started, action="place", ships=guest_fleet).json()
    assert guest_view["status"] == "playing"

    host_view = client.get(f"/api/games/sea/{code}", headers=host).json()
    shooter, waiter = (host, guest) if host_view["my_turn"] else (guest, host)
    shooter_view = client.get(f"/api/games/sea/{code}", headers=shooter).json()
    waiter_view = client.get(f"/api/games/sea/{code}", headers=waiter).json()
    assert _move(client, waiter, waiter_view, action="fire", cell=0).status_code == 400
    assert _move(client, shooter, shooter_view, action="fire", cell=0).status_code == 200
    assert _move(client, shooter, shooter_view, action="fire", cell=1).status_code == 409

    # У соперника выстрел подсвечен на его доске.
    waiter_view = client.get(f"/api/games/sea/{code}", headers=waiter).json()
    assert "0" in waiter_view["my_board"]["shots"] and waiter_view["my_board"]["recent"] == [0]

    resigned = _move(client, waiter, waiter_view, action="resign").json()
    assert resigned["status"] == "finished" and resigned["result"] == "lose"
    assert client.get("/api/games/sea", headers=shooter).json() == []


def test_guest_misses_ready_check(client, monkeypatch, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = client.post("/api/games/sea", json={"vs_bot": False}, headers=host).json()["code"]
    client.post(f"/api/games/sea/{code}/join", json={}, headers=guest)
    client.post(f"/api/games/sea/{code}/ready", headers=host)
    future = sea_battle_service._now() + datetime.timedelta(seconds=10)
    monkeypatch.setattr(sea_battle_service, "_now", lambda: future)
    reopened = client.get(f"/api/games/sea/{code}", headers=host).json()
    assert reopened["status"] == "waiting" and reopened["opponent"] is None


def test_host_cancels_waiting_game(client, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = client.post("/api/games/sea", json={"vs_bot": False}, headers=host).json()["code"]

    # Закрыть лобби может только создатель.
    assert client.post(f"/api/games/sea/{code}/cancel", headers=guest).status_code == 400

    cancelled = client.post(f"/api/games/sea/{code}/cancel", headers=host).json()
    assert cancelled["status"] == "cancelled"
    assert client.get("/api/games/sea", headers=host).json() == []
    assert client.post(f"/api/games/sea/{code}/cancel", headers=host).json()["status"] == "cancelled"


def test_cannot_cancel_started_game(client, employee_credentials, manager_credentials):
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = client.post("/api/games/sea", json={"vs_bot": False}, headers=host).json()["code"]
    client.post(f"/api/games/sea/{code}/join", json={}, headers=guest)
    client.post(f"/api/games/sea/{code}/ready", headers=host)
    started = client.post(f"/api/games/sea/{code}/ready", headers=guest).json()
    assert started["status"] == "placing"
    assert client.post(f"/api/games/sea/{code}/cancel", headers=host).status_code == 400


def test_stale_waiting_game_expires(client, monkeypatch, employee_credentials):
    host = _auth(client, employee_credentials)
    code = client.post("/api/games/sea", json={"vs_bot": False}, headers=host).json()["code"]

    future = sea_battle_service._now() + datetime.timedelta(
        hours=sea_battle_service.WAITING_TTL_HOURS, minutes=1
    )
    monkeypatch.setattr(sea_battle_service, "_now", lambda: future)
    assert client.get(f"/api/games/sea/{code}", headers=host).json()["status"] == "cancelled"
    assert client.get("/api/games/sea", headers=host).json() == []


def test_chat_invite(client, monkeypatch, employee_credentials, manager_credentials):
    sent, edits = [], []
    monkeypatch.setattr(settings, "telegram_games_chat_id", -100500)
    monkeypatch.setattr(telegram_service, "telegram_enabled", lambda: True)
    monkeypatch.setattr(telegram_service, "startapp_url", lambda p: f"https://t.me/ik_bot?startapp={p}")
    monkeypatch.setattr(
        telegram_service, "send_photo",
        lambda chat_id, photo, caption, buttons: sent.append((photo, caption, buttons)) or 77,
    )
    monkeypatch.setattr(
        telegram_service, "edit_caption",
        lambda chat_id, message_id, caption, buttons: edits.append((caption, buttons)),
    )
    monkeypatch.setattr("app.services.push_service.send_to_user", lambda *a, **k: None)
    host, guest = _auth(client, employee_credentials), _auth(client, manager_credentials)
    code = client.post("/api/games/sea", json={"vs_bot": False}, headers=host).json()["code"]
    invited = client.post(f"/api/games/sea/{code}/invite-chat", headers=host).json()
    assert invited["chat_invite"]["sent"]
    photo, caption, buttons = sent[0]
    assert photo.endswith("/og/sea-invite.png") and "Морской бой" in caption
    assert buttons[0]["url"] == f"https://t.me/ik_bot?startapp=sea_{code}"
    client.post(f"/api/games/sea/{code}/join", json={}, headers=guest)
    assert "Маша Менеджер" in edits[-1][0] and edits[-1][1] is None
