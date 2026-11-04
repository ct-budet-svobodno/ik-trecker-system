import random

import pytest

from app.core.config import settings
from app.games import bunker
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services import telegram_service, user_service
from tests.conftest import TestingSessionLocal


def _players(client, count):
    """Завести count игроков и вернуть их заголовки авторизации."""
    headers = []
    db = TestingSessionLocal()
    try:
        for i in range(count):
            user_service.create_user(
                db,
                UserCreate(
                    full_name=f"Игрок {i}", username=f"player{i}", password="playerpass1", role=UserRole.EMPLOYEE
                ),
            )
    finally:
        db.close()
    for i in range(count):
        token = client.post(
            "/api/auth/login", data={"username": f"player{i}", "password": "playerpass1"}
        ).json()["access_token"]
        headers.append({"Authorization": f"Bearer {token}"})
    return headers


def _move(client, headers, code, **payload):
    view = client.get(f"/api/games/bunker/{code}", headers=headers).json()
    return client.post(
        f"/api/games/bunker/{code}/move", json={**payload, "version": view["version"]}, headers=headers
    )


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr("app.services.push_service.send_to_users", lambda *a, **k: None)


# ── Механика ──

@pytest.mark.parametrize("players", range(bunker.MIN_PLAYERS, bunker.MAX_PLAYERS + 1))
def test_schedule_leaves_seats(players):
    plan = bunker.schedule(players)
    assert len(plan) == bunker.ROUNDS
    assert players - sum(plan) == bunker.seats_for(players) == players // 2
    assert plan == sorted(plan)  # выгоняют ближе к концу


def test_deal_has_unique_cards():
    state = bunker.new_game(bunker.MAX_PLAYERS, random.Random(1))
    for category in ("profession", "health", "hobby", "baggage", "fact"):
        values = [p["cards"][category].split(",")[0] for p in state["players"]]
        assert len(set(values)) == len(values) or category == "health"
    assert all(p["revealed"] == ["profession"] for p in state["players"])


@pytest.mark.parametrize("players", [4, 7, 12, 16])
def test_full_game_leaves_seats(players):
    rng = random.Random(players)
    state = bunker.new_game(players, rng)
    for _ in range(200):
        if bunker.over(state):
            break
        phase = state["phase"]
        if phase == "reveal":
            for seat in bunker.active(state):
                hidden = [c for c in bunker.CATEGORIES if c not in state["players"][seat]["revealed"]]
                bunker.reveal(state, seat, rng.choice(hidden))
        elif phase == "vote":
            pool = state["candidates"] or bunker.active(state)
            for seat in bunker.active(state):
                if state["phase"] == "vote":
                    bunker.vote(state, seat, rng.choice([t for t in pool if t != seat]), rng)
        else:
            bunker.advance(state, rng)
    assert bunker.over(state)
    assert len(bunker.active(state)) == state["seats"]
    assert all(len(p["revealed"]) == len(bunker.CATEGORIES) for p in state["players"])


def test_tie_revote_then_lot():
    state = bunker.new_game(4)
    state["round"] = bunker.ROUNDS - 1  # раунд с изгнанием
    state["phase"] = "vote"
    # 0↔1 и 2↔3: ничья между всеми.
    for seat, target in ((0, 1), (1, 0), (2, 3), (3, 2)):
        bunker.vote(state, seat, target)
    assert state["last_vote"]["tie"] and state["candidates"] == [0, 1, 2, 3]
    assert not any(p["out"] for p in state["players"])

    bunker.advance(state)
    assert state["phase"] == "vote"
    for seat, target in ((0, 1), (1, 0), (2, 3), (3, 2)):
        bunker.vote(state, seat, target, random.Random(0))
    result = state["last_vote"]
    assert result["lot"] and result["out"] in (0, 1, 2, 3)
    assert state["players"][result["out"]]["out"]
    assert state["candidates"] is None


def test_rules():
    state = bunker.new_game(4)
    bunker.reveal(state, 0, "health")
    with pytest.raises(bunker.IllegalMove):
        bunker.reveal(state, 0, "hobby")  # одна карта за раунд
    with pytest.raises(bunker.IllegalMove):
        bunker.reveal(state, 1, "profession")  # уже открыта
    with pytest.raises(bunker.IllegalMove):
        bunker.vote(state, 1, 2)  # не фаза голосования
    with pytest.raises(bunker.IllegalMove):
        bunker.new_game(3)


# ── API ──

def test_lobby_and_game_flow(client):
    host, *others = _players(client, 4)
    created = client.post("/api/games/bunker", headers=host)
    assert created.status_code == 201
    code = created.json()["code"]

    # Мало игроков — начать нельзя.
    assert client.post(f"/api/games/bunker/{code}/start", headers=host).status_code == 400
    for h in others:
        assert client.post(f"/api/games/bunker/{code}/join", headers=h).json()["seat"] is not None
    # Выйти и вернуться.
    client.post(f"/api/games/bunker/{code}/leave", headers=others[0])
    lobby = client.get(f"/api/games/bunker/{code}", headers=host).json()
    assert [p["full_name"] for p in lobby["players"]] == ["Игрок 0", "Игрок 2", "Игрок 3"]
    client.post(f"/api/games/bunker/{code}/join", headers=others[0])

    # Начать может только создатель.
    assert client.post(f"/api/games/bunker/{code}/start", headers=others[0]).status_code == 400
    started = client.post(f"/api/games/bunker/{code}/start", headers=host).json()
    assert started["status"] == "playing" and started["seats"] == 2 and started["phase"] == "reveal"

    # Свои карты видны все, чужие — только открытые.
    me = started["players"][started["seat"]]
    assert len(me["cards"]) == 7 and "profession" not in me["hidden"]
    other = next(p for p in started["players"] if p["seat"] != started["seat"])
    assert list(other["cards"]) == ["profession"] and other["hidden"] == []

    # Лобби закрыто для новых.
    late = _players_extra(client)
    assert client.get(f"/api/games/bunker/{code}", headers=late).status_code == 404

    everyone = [host, *others]
    for h in everyone:
        assert _move(client, h, code, action="reveal", category="health").status_code == 200
    view = client.get(f"/api/games/bunker/{code}", headers=others[1]).json()
    assert view["phase"] == "discuss"
    assert all("health" in p["cards"] for p in view["players"])

    # «Дальше» — только создатель и по свежей версии.
    assert _move(client, others[1], code, action="advance").status_code == 400
    stale = client.post(
        f"/api/games/bunker/{code}/move", json={"action": "advance", "version": 1}, headers=host
    )
    assert stale.status_code == 409


def _players_extra(client):
    db = TestingSessionLocal()
    try:
        user_service.create_user(
            db, UserCreate(full_name="Опоздавший", username="late", password="playerpass1", role=UserRole.EMPLOYEE)
        )
    finally:
        db.close()
    token = client.post("/api/auth/login", data={"username": "late", "password": "playerpass1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_full_game_via_api(client):
    headers = _players(client, 4)
    code = client.post("/api/games/bunker", headers=headers[0]).json()["code"]
    for h in headers[1:]:
        client.post(f"/api/games/bunker/{code}/join", headers=h)
    client.post(f"/api/games/bunker/{code}/start", headers=headers[0])

    for _ in range(100):
        view = client.get(f"/api/games/bunker/{code}", headers=headers[0]).json()
        if view["status"] == "finished":
            break
        if view["phase"] == "reveal":
            for h in headers:
                v = client.get(f"/api/games/bunker/{code}", headers=h).json()
                mine = v["players"][v["seat"]]
                if not mine["out"] and not mine["revealed_now"]:
                    _move(client, h, code, action="reveal", category=mine["hidden"][0])
        elif view["phase"] == "vote":
            # Все против одного — без ничьих.
            pool = view["candidates"] or [p["seat"] for p in view["players"] if not p["out"]]
            target = pool[-1]
            for h in headers:
                v = client.get(f"/api/games/bunker/{code}", headers=h).json()
                if v["phase"] != "vote" or v["players"][v["seat"]]["out"]:
                    continue
                vote_for = target if v["seat"] != target else pool[0]
                assert _move(client, h, code, action="vote", target=vote_for).status_code == 200
        else:
            assert _move(client, headers[0], code, action="advance").status_code == 200

    final = client.get(f"/api/games/bunker/{code}", headers=headers[1]).json()
    assert final["status"] == "finished" and final["phase"] == "over"
    assert sum(not p["out"] for p in final["players"]) == 2
    assert all(len(p["cards"]) == 7 for p in final["players"])
    assert client.get("/api/games/bunker", headers=headers[1]).json() == []


def test_chat_invite(client, monkeypatch):
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
    host, guest = _players(client, 2)
    code = client.post("/api/games/bunker", headers=host).json()["code"]
    assert client.post(f"/api/games/bunker/{code}/invite-chat", headers=host).json()["chat_invite"]["sent"]
    photo, caption, buttons = sent[0]
    assert photo.endswith("/og/bunker-invite.png") and "1 из 16" in caption
    assert buttons[0]["url"] == f"https://t.me/ik_bot?startapp=bunker_{code}"
    client.post(f"/api/games/bunker/{code}/join", headers=guest)
    assert "2 из 16" in edits[-1][0]
    _move(client, host, code, action="stop")
    assert "отменена" in edits[-1][0] and edits[-1][1] is None


# ── Столы из админки ──

def _tagged(client, count):
    """count игроков с Telegram-тегами tag0…; вернуть их заголовки."""
    headers = _players(client, count)
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        for i in range(count):
            user = db.query(User).filter(User.username == f"player{i}").one()
            user.telegram_username = f"Tag{i}"
        db.commit()
    finally:
        db.close()
    return headers


def test_admin_table_with_observer_host(client, admin_credentials):
    admin = {"Authorization": "Bearer " + client.post("/api/auth/login", data=admin_credentials).json()["access_token"]}
    players = _tagged(client, 5)

    # Не админ столы не заводит.
    assert client.post("/api/games/bunker/tables", json={"title": "Стол 1"}, headers=players[0]).status_code == 403

    saved = client.post(
        "/api/games/bunker/tables",
        json={"title": "Стол 1", "tags": ["@tag0, tag1", "TAG2\ntag3", "ghost"]},
        headers=admin,
    ).json()
    assert saved["missing"] == ["ghost"]
    table = saved["table"]
    code = table["code"]
    assert [p["tag"] for p in table["players"]] == ["Tag0", "Tag1", "Tag2", "Tag3"]
    assert table["host"]["full_name"] == "Admin Adminovich" and not table["host_plays"]

    # Игрок стола видит его.
    lobby = client.get(f"/api/games/bunker/{code}", headers=players[0]).json()
    assert lobby["title"] == "Стол 1" and not lobby["is_host"] and lobby["invite_url"]
    # Стол виден в открытых тем, кого за ним нет; сесть можно самому и выйти.
    assert [t["code"] for t in client.get("/api/games/bunker/open-tables", headers=players[4]).json()] == [code]
    assert client.get("/api/games/bunker/open-tables", headers=players[0]).json() == []
    joined = client.post(f"/api/games/bunker/{code}/join", headers=players[4]).json()
    assert joined["seat"] == 4
    assert client.post(f"/api/games/bunker/{code}/leave", headers=players[4]).status_code == 200

    # Поменять состав до раздачи.
    updated = client.put(
        f"/api/games/bunker/tables/{code}",
        json={"title": "Стол 1", "tags": ["tag0", "tag1", "tag2", "tag4"]},
        headers=admin,
    ).json()
    assert [p["tag"] for p in updated["table"]["players"]] == ["Tag0", "Tag1", "Tag2", "Tag4"]
    # Убранный админом — снова просто посторонний: стол виден ему как открытый.
    assert client.get(f"/api/games/bunker/{code}", headers=players[3]).json()["can_join"]

    started = client.post(f"/api/games/bunker/tables/{code}/start", headers=admin).json()
    assert started["status"] == "playing"
    assert client.put(
        f"/api/games/bunker/tables/{code}", json={"title": "x", "tags": ["tag0"]}, headers=admin
    ).status_code == 400
    # После раздачи сесть уже нельзя.
    assert client.get(f"/api/games/bunker/{code}", headers=players[3]).status_code == 404
    assert client.get("/api/games/bunker/open-tables", headers=players[3]).json() == []

    # Ведущий-наблюдатель видит все карты, но не играет; ведёт фазы.
    host_view = client.get(f"/api/games/bunker/{code}", headers=admin).json()
    assert host_view["observer"] and host_view["seat"] is None
    assert all(len(p["cards"]) == 7 for p in host_view["players"])
    assert _move(client, admin, code, action="reveal", category="health").status_code == 400
    # Игрок видит у соседей только открытое.
    player_view = client.get(f"/api/games/bunker/{code}", headers=players[0]).json()
    assert not player_view["observer"]
    assert all(len(p["cards"]) == 1 for p in player_view["players"] if p["seat"] != player_view["seat"])
    assert _move(client, admin, code, action="advance").json()["phase"] == "discuss"

    assert [t["code"] for t in client.get("/api/games/bunker/tables", headers=admin).json()] == [code]
    assert client.get("/api/games/bunker", headers=admin).json()[0]["code"] == code


def test_table_host_by_tag_and_too_many(client, admin_credentials):
    admin = {"Authorization": "Bearer " + client.post("/api/auth/login", data=admin_credentials).json()["access_token"]}
    players = _tagged(client, 4)
    saved = client.post(
        "/api/games/bunker/tables",
        json={"title": "Стол 2", "tags": ["tag0", "tag1", "tag2", "tag3"], "host_tag": "@tag1"},
        headers=admin,
    ).json()
    assert saved["table"]["host"]["tag"] == "Tag1" and saved["table"]["host_plays"]
    code = saved["table"]["code"]
    # Играющий ведущий начинает сам и видит только свои закрытые карты.
    started = client.post(f"/api/games/bunker/{code}/start", headers=players[1]).json()
    assert started["status"] == "playing" and not started["observer"]
    too_many = [f"t{i}" for i in range(17)]
    assert client.post(
        "/api/games/bunker/tables", json={"title": "Стол 3", "tags": too_many}, headers=admin
    ).status_code == 201  # не найденные не считаются


def test_table_edit_keeps_untagged_joiners(client, admin_credentials):
    admin = {"Authorization": "Bearer " + client.post("/api/auth/login", data=admin_credentials).json()["access_token"]}
    _tagged(client, 4)
    untagged = _players_extra(client)  # без Telegram-тега, вход из браузера
    code = client.post(
        "/api/games/bunker/tables", json={"title": "Стол", "tags": ["tag0", "tag1", "tag2"]}, headers=admin
    ).json()["table"]["code"]
    client.post(f"/api/games/bunker/{code}/join", headers=untagged)
    updated = client.put(
        f"/api/games/bunker/tables/{code}", json={"title": "Стол", "tags": ["tag0", "tag3"]}, headers=admin
    ).json()["table"]
    assert [p["full_name"] for p in updated["players"]] == ["Игрок 0", "Игрок 3", "Опоздавший"]


def test_empty_table_players_join_themselves(client, admin_credentials, monkeypatch):
    pushed = []
    monkeypatch.setattr(
        "app.services.push_service.send_to_users", lambda db, ids, **kw: pushed.append((list(ids), kw["body"]))
    )
    admin = {"Authorization": "Bearer " + client.post("/api/auth/login", data=admin_credentials).json()["access_token"]}
    players = _players(client, 4)
    codes = [
        client.post("/api/games/bunker/tables", json={"title": f"Стол {i}"}, headers=admin).json()["table"]["code"]
        for i in (1, 2)
    ]
    assert pushed == []  # пустые столы, ведёт сам админ — никого не дёргаем
    open_tables = client.get("/api/games/bunker/open-tables", headers=players[0]).json()
    assert sorted(t["code"] for t in open_tables) == sorted(codes)
    for h in players:
        client.post(f"/api/games/bunker/{codes[0]}/join", headers=h)
    table = client.get("/api/games/bunker/tables", headers=admin).json()
    seated = next(t for t in table if t["code"] == codes[0])
    assert len(seated["players"]) == 4 and not seated["host_plays"]
    assert client.post(f"/api/games/bunker/tables/{codes[0]}/start", headers=admin).json()["status"] == "playing"
    # Каждый игрок сразу видит своего персонажа целиком.
    me = client.get(f"/api/games/bunker/{codes[0]}", headers=players[2]).json()
    assert len(me["players"][me["seat"]]["cards"]) == 7
