import sqlite3

import pytest

from app.core.config import settings
from app.models.user import User
from app.models.user_profile import UserProfile
from tests.conftest import TestingSessionLocal
from tests.test_bot_sync import BOT_SCHEMA
from tests.test_telegram_auth import BOT_TOKEN, _auth_headers, _init_data, _login, _tg_login

ACTIVISTS = """
INSERT INTO activists (id, tg_username, fio, email, studak, "group", phone, clothes_size, someone_div,
                       birthday, is_active, ik_div) VALUES
  (1, '@Anna_B', 'Белова Анна Сергеевна', 'anna@gmail.com', 1, 'РИ-1', '79990000001', 'S', '',
   '2005-03-14 00:00:00.000000', 1, 'дизайн, сми'),
  (2, 'ivan', 'Иванов Иван', '', 2, '', '', 'L', '', NULL, 1, 'f&u prod.'),
  (3, 'gone', 'Ушедший Человек', '', 3, '', '', 'M', '', NULL, 0, 'тупа выпускник'),
  (4, '@manager_tag', 'Маша Менеджер', '', 4, '', '', 'M', '', NULL, 1, 'сми'),
  (5, 'petr_ik', 'Петров Пётр', '', 5, 'РИ-5', '79990000005', 'M', '', '2004-01-02 00:00:00', 1, 'фото');
INSERT INTO activist_links (tg_id, activist_id, username) VALUES (5001, 1, 'Anna_B');
INSERT INTO activist_photos (activist_id, slot, file_id) VALUES (1, 1, 'FILE_1'), (1, 2, 'FILE_2');
"""


@pytest.fixture()
def bot_db(monkeypatch, tmp_path, direction, smi_direction):
    path = tmp_path / "bot.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(BOT_SCHEMA + ACTIVISTS)
    monkeypatch.setattr(settings, "bot_db_path", str(path))
    monkeypatch.setattr(settings, "telegram_bot_token", BOT_TOKEN)
    monkeypatch.setattr("app.services.telegram_service.telegram_enabled", lambda: False)
    return path


def _users():
    db = TestingSessionLocal()
    try:
        return {u.full_name: u for u in db.query(User).all()}
    finally:
        db.close()


def test_import_all(client, admin_credentials, manager_credentials, employee_credentials, bot_db):
    # У менеджера в трекере уже стоит тег, но Telegram не привязан — не дублируем.
    db = TestingSessionLocal()
    db.query(User).filter(User.username == "manager").one().telegram_username = "Manager_Tag"
    db.commit()
    db.close()

    admin = _auth_headers(_login(client, admin_credentials))
    assert client.post("/api/users/import-from-bot", headers=_auth_headers(_login(client, employee_credentials))).status_code == 403
    report = client.post("/api/users/import-from-bot", headers=admin).json()
    # Менеджеру без направлений дописали СМИ из анкеты бота.
    assert (report["created"], report["linked"]) == (3, 1)
    assert sorted(report["names"]) == ["Белова Анна Сергеевна", "Иванов Иван", "Петров Пётр"]

    users = _users()
    assert "Ушедший Человек" not in users  # неактивных не переносим
    anna = users["Белова Анна Сергеевна"]
    assert (anna.username, anna.telegram_id, anna.telegram_username) == ("tg5001", 5001, "Anna_B")
    assert anna.is_active and anna.registration_status.value == "approved" and anna.role.value == "employee"
    assert anna.is_activist
    ivan = users["Иванов Иван"]
    assert (ivan.username, ivan.telegram_id, ivan.telegram_username) == ("bot2", None, "ivan")

    db = TestingSessionLocal()
    profile = db.get(UserProfile, anna.id)
    assert str(profile.birthday) == "2005-03-14" and profile.phone == "79990000001"
    assert profile.direction.short_code == "Дизайн"  # в анкете одно — первое из «дизайн, сми»
    assert [d.short_code for d in db.get(User, anna.id).directions] == ["Дизайн", "СМИ"]
    assert [d.short_code for d in db.query(User).filter(User.username == "manager").one().directions] == ["СМИ"]
    assert (profile.photo1_file_id, profile.photo2_file_id) == ("FILE_1", "FILE_2")
    assert db.get(UserProfile, ivan.id) is None  # без ДР анкету не заводим
    db.close()

    # Повторный импорт ничего не плодит.
    again = client.post("/api/users/import-from-bot", headers=admin).json()
    assert again["created"] == 0 and len(_users()) == len(users)


def test_login_without_second_form(client, manager_credentials, bot_db):
    # Анкета есть только в боте (по тегу, без привязки) — вход сразу, аккаунт заводится.
    response = _tg_login(client, _init_data({"id": 777000111, "first_name": "Пётр", "username": "petr_ik"}))
    assert response.status_code == 200
    petr = _users()["Петров Пётр"]
    assert petr.telegram_id == 777000111 and petr.is_active

    # Аккаунт в трекере с тем же тегом, но без Telegram — привязываем, а не заводим дубль.
    db = TestingSessionLocal()
    db.query(User).filter(User.username == "manager").one().telegram_username = "masha"
    db.commit()
    db.close()
    assert _tg_login(client, _init_data({"id": 888, "first_name": "Маша", "username": "Masha"})).status_code == 200
    assert _users()["Маша Менеджер"].telegram_id == 888

    # Нигде нет — как раньше, 404 и анкета в мини-аппе.
    assert _tg_login(client, _init_data({"id": 999, "first_name": "Новый", "username": "nobody"})).status_code == 404


def test_disabled_without_bot_db(client, admin_credentials, monkeypatch, bot_db):
    monkeypatch.setattr(settings, "bot_db_path", None)
    admin = _auth_headers(_login(client, admin_credentials))
    assert client.post("/api/users/import-from-bot", headers=admin).json()["created"] == 0
