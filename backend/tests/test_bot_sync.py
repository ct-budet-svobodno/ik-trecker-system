import sqlite3

import pytest

from app.core.config import settings
from app.models.user_profile import UserProfile
from tests.conftest import TestingSessionLocal
from tests.test_registration import _register
from tests.test_telegram_auth import BOT_TOKEN, TG_USER, _auth_headers, _login

# Схема как в боевой базе бота (bot/database: models.py, profile_models.py).
BOT_SCHEMA = """
CREATE TABLE activists (
    id INTEGER NOT NULL, tg_username VARCHAR NOT NULL, fio VARCHAR NOT NULL,
    email VARCHAR NOT NULL, studak INTEGER NOT NULL, "group" VARCHAR NOT NULL,
    phone VARCHAR NOT NULL, clothes_size INTEGER NOT NULL, someone_div VARCHAR NOT NULL,
    birthday DATETIME, is_active BOOLEAN NOT NULL, ik_div VARCHAR NOT NULL, PRIMARY KEY (id)
);
CREATE TABLE activist_links (
    tg_id BIGINT NOT NULL, activist_id INTEGER NOT NULL, username VARCHAR,
    filled_at DATETIME, PRIMARY KEY (tg_id)
);
CREATE TABLE activist_photos (
    activist_id INTEGER NOT NULL, slot INTEGER NOT NULL, file_id VARCHAR NOT NULL,
    PRIMARY KEY (activist_id, slot)
);
"""


@pytest.fixture()
def bot_db(monkeypatch, tmp_path):
    path = tmp_path / "bot.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(BOT_SCHEMA)
    monkeypatch.setattr(settings, "telegram_bot_token", BOT_TOKEN)
    monkeypatch.setattr(settings, "profile_photos_dir", str(tmp_path / "photos"))
    monkeypatch.setattr(settings, "bot_db_path", str(path))
    monkeypatch.setattr("app.services.telegram_service.telegram_enabled", lambda: False)
    return path


def _approve(client, admin_credentials, file_ids=None):
    admin = _auth_headers(_login(client, admin_credentials))
    user_id = client.get("/api/users/registrations", headers=admin).json()[0]["id"]
    if file_ids:
        with TestingSessionLocal() as db:
            profile = db.get(UserProfile, user_id)
            profile.photo1_file_id, profile.photo2_file_id = file_ids
            db.commit()
    assert client.post(f"/api/users/{user_id}/approve", headers=admin).status_code == 200


def _rows(path, sql, params=()):
    with sqlite3.connect(path) as conn:
        return conn.execute(sql, params).fetchall()


def test_approved_profile_appears_in_bot(client, admin_credentials, bot_db, direction):
    _register(client, direction_id=str(direction.id))
    # До одобрения в базе бота ничего нет.
    assert _rows(bot_db, "SELECT count(*) FROM activists") == [(0,)]

    _approve(client, admin_credentials, file_ids=["FILE_A", "FILE_B"])
    activists = _rows(
        bot_db, 'SELECT id, tg_username, fio, phone, email, "group", clothes_size, ik_div, birthday, is_active FROM activists'
    )
    assert len(activists) == 1
    aid, tag, fio, phone, email, group, size, div, birthday, active = activists[0]
    assert (tag, fio, phone, email, group, size) == (
        TG_USER["username"], "Петров Пётр Петрович", "79991234567", "petr@urfu.me", "РИ-410015", "M",
    )
    assert div == direction.short_code and birthday.startswith("2004-05-17") and active == 1
    assert _rows(bot_db, "SELECT tg_id, activist_id FROM activist_links") == [(TG_USER["id"], aid)]
    assert _rows(bot_db, "SELECT slot, file_id FROM activist_photos ORDER BY slot") == [(1, "FILE_A"), (2, "FILE_B")]


def test_existing_activist_found_by_tag_is_updated(client, admin_credentials, bot_db):
    # Человек уже в базе бота из Excel: тег с «@» и другим регистром, без привязки.
    with sqlite3.connect(bot_db) as conn:
        conn.execute(
            "INSERT INTO activists (id, tg_username, fio, email, studak, \"group\", phone, clothes_size, "
            "someone_div, birthday, is_active, ik_div) VALUES (7, '@Petr_IK', 'Петров П.', '', 123456, '', '', '', '', NULL, 1, 'фото')"
        )
    _register(client)
    _approve(client, admin_credentials)
    rows = _rows(bot_db, "SELECT id, fio, studak, phone, ik_div FROM activists")
    # Дубля нет, студак сохранён; направления из анкеты нет (не выбрано) — «фото» осталось.
    assert rows == [(7, "Петров Пётр Петрович", 123456, "79991234567", "фото")]
    assert _rows(bot_db, "SELECT activist_id FROM activist_links") == [(7,)]


def test_sync_disabled_without_bot_db(client, admin_credentials, bot_db, monkeypatch):
    monkeypatch.setattr(settings, "bot_db_path", None)
    _register(client)
    _approve(client, admin_credentials)
    assert _rows(bot_db, "SELECT count(*) FROM activists") == [(0,)]


@pytest.mark.parametrize(
    "existing, code, expected",
    [
        ("", "ЦТ", "ЦТ"),
        ("дизайн, цт", "ЦТ", "дизайн, цт"),
        ("тупа выпускник, фото", "Дизайн", "тупа выпускник, фото, Дизайн"),
        ("f&u prod., тупа выпускник", "Прод", "f&u prod., тупа выпускник"),
        ("фото", None, "фото"),
    ],
)
def test_direction_merge(existing, code, expected):
    from app.services.bot_sync_service import merge_direction

    assert merge_direction(existing, code) == expected
