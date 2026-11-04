import io
import json
import random
import sqlite3
import urllib.error
from collections import Counter

import pytest

from app.activities.checklist_facts import DEFAULT_FACTS
from app.core.config import settings
from app.services import checklist_service, telegram_service
from tests.conftest import TestingSessionLocal

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


def _auth(client, credentials):
    token = client.post("/api/auth/login", data=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def bot(monkeypatch, tmp_path):
    path = tmp_path / "bot.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE activists (id INTEGER PRIMARY KEY, fio VARCHAR, tg_username VARCHAR);
            CREATE TABLE activist_links (tg_id BIGINT PRIMARY KEY, activist_id INTEGER, username VARCHAR, filled_at DATETIME);
            CREATE TABLE stats_users (user_id BIGINT PRIMARY KEY, username VARCHAR, full_name VARCHAR, last_seen DATETIME);
            INSERT INTO activists VALUES (1, 'Петров Пётр', '@petr'), (2, 'Анна Белова', 'anna');
            INSERT INTO activist_links (tg_id, activist_id) VALUES (101, 1), (102, 2);
            INSERT INTO stats_users (user_id, username, full_name) VALUES (102, 'anna_b', 'Аня'), (103, 'vasya', 'Вася Чатов');
            CREATE TABLE bot_contacts (tg_id BIGINT PRIMARY KEY, username VARCHAR, full_name VARCHAR, last_seen DATETIME);
            """
        )
    monkeypatch.setattr(settings, "bot_db_path", str(path))
    monkeypatch.setattr(settings, "telegram_bot_token", "123:TEST")
    monkeypatch.setattr(settings, "checklist_images_dir", str(tmp_path / "checklists"))
    sent = []

    blocked = {103}

    def fake_send(chat_id, data, caption, filename="photo.jpg"):
        if chat_id in blocked:
            raise urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b"{}"))
        # Строка в базе бота уже есть, когда лист уходит.
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT 1 FROM checklists WHERE tg_id = ?", (chat_id,)).fetchone()
        sent.append((chat_id, caption))
        return {"message_id": 1}

    monkeypatch.setattr(telegram_service, "send_photo_file", fake_send)
    monkeypatch.setattr(checklist_service, "_spawn", lambda target, *args: target(*args))
    monkeypatch.setattr(checklist_service, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(checklist_service, "SEND_INTERVAL", 0)
    return path, sent, blocked


@pytest.mark.parametrize("people", [1, 7, 37, 50, 81, 120])
def test_deal_is_balanced_and_without_repeats(people):
    cards = checklist_service.deal(DEFAULT_FACTS, people, random.Random(people))
    assert len(cards) == people
    assert all(len(set(card)) == 3 for card in cards)
    counts = Counter(f for card in cards for f in card)
    if people * 3 >= len(DEFAULT_FACTS):
        assert set(counts) == set(DEFAULT_FACTS)  # каждый факт кому-то достался
    assert max(counts.values()) - min(counts.values()) <= 1 or people * 3 < len(DEFAULT_FACTS)


def test_flow(client, admin_credentials, employee_credentials, bot):
    path, sent, blocked = bot
    employee = _auth(client, employee_credentials)
    assert client.get("/api/checklists", headers=employee).status_code == 403
    admin = _auth(client, admin_credentials)

    overview = client.get("/api/checklists", headers=admin).json()
    assert overview["enabled"] and overview["cards"] == [] and len(overview["default_facts"]) == 109

    facts = ["тем, кто А", "тем, кто Б", "тем, кто В", "тем, кто Г", " ", "тем, кто А"]
    cards = client.post("/api/checklists/prepare", json={"facts": facts}, headers=admin).json()["cards"]
    # Имена: из анкеты бота главнее имени из чата; отсортированы и пронумерованы.
    assert [(c["number"], c["full_name"], c["username"]) for c in cards] == [
        (1, "Анна Белова", "anna"), (2, "Вася Чатов", "vasya"), (3, "Петров Пётр", "petr"),
    ]
    assert all(len(set(c["facts"])) == 3 for c in cards)

    # Без картинок не разослать.
    assert client.post("/api/checklists/send", headers=admin).status_code == 400
    assert client.put(
        f"/api/checklists/cards/{cards[0]['id']}/image", files={"image": ("a.png", b"PNG", "image/png")}, headers=admin
    ).status_code == 400
    for card in cards:
        assert client.put(
            f"/api/checklists/cards/{card['id']}/image", files={"image": ("c.jpg", JPEG, "image/jpeg")}, headers=admin
        ).status_code == 204
    assert client.get(f"/api/checklists/cards/{cards[0]['id']}/image", headers=admin).content == JPEG

    # Проверка на себе: без Telegram — понятная ошибка; с ним уходит только свой лист.
    assert client.post("/api/checklists/send-test", headers=admin).status_code == 400
    db = TestingSessionLocal()
    from app.models.user import User
    db.query(User).filter(User.username == "admin").one().telegram_id = 101
    db.commit()
    db.close()
    tested = client.post("/api/checklists/send-test", headers=admin).json()["cards"]
    assert [c["status"] for c in tested] == ["draft", "draft", "sent"] and [chat for chat, _ in sent] == [101]

    result = client.post("/api/checklists/send", headers=admin).json()
    statuses = {c["full_name"]: c["status"] for c in result["cards"]}
    assert statuses == {"Анна Белова": "sent", "Вася Чатов": "failed", "Петров Пётр": "sent"}
    assert sorted(chat for chat, _ in sent) == [101, 102]  # свой лист повторно не ушёл
    anna_caption = next(c for chat, c in sent if chat == 102)
    assert "Чек-лист №1" in anna_caption and "1. Сфоткайся с тем, кто" in anna_caption

    with sqlite3.connect(path) as conn:
        rows = dict(conn.execute("SELECT tg_id, facts FROM checklists").fetchall())
        assert sorted(rows) == [101, 102]  # недоставленному приём фото не открываем
        assert json.loads(rows[102]) == cards[0]["facts"]
        # Бот принял два фото от Анны.
        conn.execute("UPDATE checklists SET photo1 = 'F1', photo3 = 'F3' WHERE tg_id = 102")
    progress = client.get("/api/checklists", headers=admin).json()["cards"]
    assert progress[0]["photos"] == [True, False, True]

    # Пока разослано — заново не раздать; после сброса всё чисто.
    assert client.post("/api/checklists/prepare", json={"facts": facts}, headers=admin).status_code == 400
    assert client.post("/api/checklists/reset", headers=admin).json()["cards"] == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM checklists").fetchone() == (0,)


def test_send_by_tag(client, admin_credentials, bot):
    path, sent, blocked = bot
    admin = _auth(client, admin_credentials)
    facts = ["тем, кто А", "тем, кто Б", "тем, кто В", "тем, кто Г", "тем, кто Д"]
    cards = client.post("/api/checklists/prepare", json={"facts": facts}, headers=admin).json()["cards"]
    for card in cards:
        client.put(f"/api/checklists/cards/{card['id']}/image", files={"image": ("c.jpg", JPEG, "image/jpeg")}, headers=admin)
    client.post("/api/checklists/send", headers=admin)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE checklists SET photo1 = 'KEEP' WHERE tg_id = 101")

    # Вася не дошёл: нажал «Старт» — досылаем его же лист по тегу.
    blocked.clear()
    found = client.post("/api/checklists/by-tag", json={"username": "@Vasya"}, headers=admin).json()
    assert found["card"]["full_name"] == "Вася Чатов" and not found["needs_image"]
    after = client.post(f"/api/checklists/cards/{found['card']['id']}/send", headers=admin).json()["cards"]
    assert {c["full_name"]: c["status"] for c in after}["Вася Чатов"] == "sent"

    # Повторная отправка уже полученного листа не стирает присланные фото.
    petr = next(c for c in after if c["tg_id"] == 101)
    client.post(f"/api/checklists/cards/{petr['id']}/send", headers=admin)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT photo1 FROM checklists WHERE tg_id = 101").fetchone() == ("KEEP",)

    # Бот не знает тег — подсказка про /start.
    unknown = client.post("/api/checklists/by-tag", json={"username": "newbie"}, headers=admin)
    assert unknown.status_code == 400 and "/start" in unknown.json()["detail"]

    # Написал боту в личку — получает новый свободный лист из самых редких фактов.
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO bot_contacts (tg_id, username, full_name) VALUES (104, 'Newbie', 'Новенький')")
    counts = {}
    for c in after:
        for f in c["facts"]:
            counts[f] = counts.get(f, 0) + 1
    fresh = client.post("/api/checklists/by-tag", json={"username": "newbie"}, headers=admin).json()
    card = fresh["card"]
    assert fresh["needs_image"] and card["number"] == 4 and card["full_name"] == "Новенький"
    assert len(set(card["facts"])) == 3
    assert max(counts.get(f, 0) for f in card["facts"]) <= min(counts.get(f, 0) for f in facts if f not in card["facts"])
    assert client.post(f"/api/checklists/cards/{card['id']}/send", headers=admin).status_code == 400  # без картинки
    client.put(f"/api/checklists/cards/{card['id']}/image", files={"image": ("c.jpg", JPEG, "image/jpeg")}, headers=admin)
    assert client.post(f"/api/checklists/cards/{card['id']}/send", headers=admin).status_code == 200
    assert sent[-1][0] == 104 and "Чек-лист №4" in sent[-1][1]
