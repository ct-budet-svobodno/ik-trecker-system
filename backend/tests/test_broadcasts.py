import io
import sqlite3
import urllib.error

import pytest

from app.core.config import settings
from app.models.user import User
from app.services import broadcast_service, telegram_service
from tests.conftest import TestingSessionLocal


def _auth(client, credentials):
    token = client.post("/api/auth/login", data=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def bot(monkeypatch, tmp_path):
    """Бот включён, в его базе — двое из лички и один из чата (плюс группа)."""
    path = tmp_path / "bot.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE activist_links (tg_id BIGINT PRIMARY KEY, activist_id INTEGER, username VARCHAR, filled_at DATETIME);
            CREATE TABLE stats_users (user_id BIGINT PRIMARY KEY, username VARCHAR, full_name VARCHAR, last_seen DATETIME);
            INSERT INTO activist_links (tg_id, activist_id) VALUES (101, 1), (102, 2);
            INSERT INTO stats_users (user_id) VALUES (102), (103), (-100500);
            """
        )
    monkeypatch.setattr(settings, "bot_db_path", str(path))
    monkeypatch.setattr(settings, "telegram_bot_token", "123:TEST")
    sent = []

    def fake_call(method, payload, timeout=10):
        if payload["chat_id"] == 103:  # не запускал бота
            raise urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b"{}"))
        sent.append(payload)
        return {"message_id": 1}

    monkeypatch.setattr(telegram_service, "call", fake_call)
    # Отправка — сразу, в тестовой базе.
    monkeypatch.setattr(broadcast_service, "_spawn", lambda target, *args: target(*args))
    monkeypatch.setattr(broadcast_service, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(broadcast_service, "SEND_INTERVAL", 0)
    return sent


def _link_telegram(username, telegram_id):
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.username == username).one()
        user.telegram_id = telegram_id
        db.commit()
    finally:
        db.close()


MESSAGE = {
    "text": "Собрание в 18:00, **не опаздываем**",
    "buttons": [
        {"text": "Открыть игры", "path": "/games"},
        {"text": "Место", "url": "https://example.com/map"},
    ],
}


def test_broadcast_reaches_everyone_known(client, admin_credentials, bot):
    admin = _auth(client, admin_credentials)
    _link_telegram("admin", 102)  # тот же человек, что в базе бота — не дублируем
    overview = client.get("/api/broadcasts", headers=admin).json()
    assert overview["recipients"] == 3 and overview["enabled"] and overview["has_telegram"]

    created = client.post("/api/broadcasts", json=MESSAGE, headers=admin)
    assert created.status_code == 201
    result = client.get(f"/api/broadcasts/{created.json()['id']}", headers=admin).json()
    assert result["status"] == "done" and (result["sent"], result["failed"], result["total"]) == (2, 1, 3)

    assert sorted(p["chat_id"] for p in bot) == [101, 102]
    payload = bot[0]
    assert payload["text"] == "Собрание в 18:00, <b>не опаздываем</b>"
    rows = payload["reply_markup"]["inline_keyboard"]
    assert rows[0][0]["web_app"]["url"].endswith("/games")
    assert rows[1][0] == {"text": "Место", "url": "https://example.com/map"}
    assert client.get("/api/broadcasts", headers=admin).json()["items"][0]["author_name"] == "Admin Adminovich"


def test_test_send_goes_only_to_me(client, admin_credentials, bot):
    admin = _auth(client, admin_credentials)
    # Без Telegram — понятная ошибка.
    assert client.post("/api/broadcasts/test", json=MESSAGE, headers=admin).status_code == 400
    _link_telegram("admin", 555)
    assert client.post("/api/broadcasts/test", json=MESSAGE, headers=admin).status_code == 204
    assert [p["chat_id"] for p in bot] == [555]
    assert client.get("/api/broadcasts", headers=admin).json()["items"] == []


def test_only_admin_and_valid_buttons(client, admin_credentials, employee_credentials, bot):
    employee = _auth(client, employee_credentials)
    assert client.get("/api/broadcasts", headers=employee).status_code == 403
    assert client.post("/api/broadcasts", json=MESSAGE, headers=employee).status_code == 403
    admin = _auth(client, admin_credentials)
    for button in ({"text": "x"}, {"text": "x", "url": "javascript:alert(1)"}, {"text": "x", "path": "games"}):
        bad = client.post("/api/broadcasts", json={"text": "Привет", "buttons": [button]}, headers=admin)
        assert bad.status_code == 422
    assert bot == []


def test_text_is_escaped():
    assert broadcast_service.render_text("<b>x</b> & __y__") == "&lt;b&gt;x&lt;/b&gt; &amp; <i>y</i>"
