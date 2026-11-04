"""Одобренная анкета из мини-аппа → база бота flood, чтобы человека находил !инфо.

У бота своя SQLite-база (bot/database/bot.db, на сервере — /root/flood/database),
трекер подключает её томом и пишет в те же таблицы, что анкета в личке с ботом
(bot/database/profile_dao.py):
  activists        — строка анкеты (её же читают !инфо и выгрузка в Excel);
  activist_links   — Telegram-аккаунт ↔ строка анкеты;
  activist_photos  — file_id двух фото.
Человек уже есть (привязан по Telegram или найден по тегу — например, из Excel) —
его строка дополняется, дубля нет. Бот работает с той же базой одновременно,
поэтому пишем одной короткой транзакцией с ожиданием блокировки.
"""
import datetime
import logging
import sqlite3
from pathlib import Path

from app.core.config import settings
from app.models.user import User
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

MSK = datetime.timezone(datetime.timedelta(hours=3))


def enabled() -> bool:
    return bool(settings.bot_db_path) and Path(settings.bot_db_path).is_file()


# Как направления трекера пишут в базе бота руками («f&u prod.» — это Прод).
DIRECTION_ALIASES = {"прод": ("прод", "f&u prod", "f&u")}


def merge_direction(existing: str | None, code: str | None) -> str:
    """Направление в бот не затираем: у многих там развёрнуто («дизайн, цт»,
    «тупа выпускник, фото»). Нет направления из трекера — дописываем через запятую."""
    existing = (existing or "").strip()
    if not code:
        return existing
    if not existing:
        return code
    haystack = existing.lower()
    if any(alias in haystack for alias in DIRECTION_ALIASES.get(code.lower(), (code.lower(),))):
        return existing
    return f"{existing}, {code}"


def _find_activist(conn: sqlite3.Connection, tg_id: int, username: str | None) -> int | None:
    row = conn.execute("SELECT activist_id FROM activist_links WHERE tg_id = ?", (tg_id,)).fetchone()
    if row is not None:
        exists = conn.execute("SELECT 1 FROM activists WHERE id = ?", (row[0],)).fetchone()
        if exists:
            return row[0]
    tag = (username or "").strip().lstrip("@").lower()
    if not tag:
        return None
    # Теги в базе бота вразнобой — с «@» и без, в разном регистре.
    row = conn.execute(
        "SELECT id FROM activists WHERE lower(replace(tg_username, '@', '')) = ? ORDER BY id LIMIT 1",
        (tag,),
    ).fetchone()
    return row[0] if row else None


def sync_profile(user: User, profile: UserProfile, direction_code: str | None) -> int | None:
    """Записать анкету в базу бота. Вернуть id строки activists (None — выключено)."""
    if not enabled() or user.telegram_id is None:
        return None
    tag = (user.telegram_username or "").strip().lstrip("@")
    fields = {
        "fio": user.full_name,
        "email": profile.email,
        "group": profile.study_group,
        "phone": profile.phone,
        "clothes_size": profile.clothes_size,
        "someone_div": profile.other_units or "",
        "birthday": datetime.datetime.combine(profile.birthday, datetime.time()).isoformat(" "),
        "is_active": 1,
    }
    conn = sqlite3.connect(settings.bot_db_path, timeout=15)
    try:
        with conn:
            activist_id = _find_activist(conn, user.telegram_id, tag)
            current = None
            if activist_id is not None:
                current = conn.execute("SELECT ik_div FROM activists WHERE id = ?", (activist_id,)).fetchone()
            fields["ik_div"] = merge_direction(current[0] if current else None, direction_code)
            if activist_id is None:
                # «group» — служебное слово SQL, поэтому все имена колонок в кавычках.
                columns = ", ".join(f'"{c}"' for c in ["tg_username", "studak", *fields])
                marks = ", ".join("?" for _ in range(len(fields) + 2))
                cursor = conn.execute(
                    f"INSERT INTO activists ({columns}) VALUES ({marks})",
                    [tag, 0, *fields.values()],
                )
                activist_id = cursor.lastrowid
            else:
                assignments = ", ".join(f'"{c}" = ?' for c in fields)
                conn.execute(
                    f"UPDATE activists SET tg_username = ?, {assignments} WHERE id = ?",
                    [tag, *fields.values(), activist_id],
                )
            filled_at = datetime.datetime.now(MSK).replace(tzinfo=None).isoformat(" ")
            conn.execute(
                "INSERT INTO activist_links (tg_id, activist_id, username, filled_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(tg_id) DO UPDATE SET activist_id = excluded.activist_id, "
                "username = excluded.username, filled_at = excluded.filled_at",
                (user.telegram_id, activist_id, tag or None, filled_at),
            )
            for slot, file_id in ((1, profile.photo1_file_id), (2, profile.photo2_file_id)):
                if file_id:
                    conn.execute(
                        "INSERT INTO activist_photos (activist_id, slot, file_id) VALUES (?, ?, ?) "
                        "ON CONFLICT(activist_id, slot) DO UPDATE SET file_id = excluded.file_id",
                        (activist_id, slot, file_id),
                    )
        return activist_id
    finally:
        conn.close()


def known_people() -> dict[int, dict]:
    """Все, кого знает бот: {tg_id: {"name", "username"}}. Заполнившие анкету
    в личке (activist_links → activists), писавшие в чатах (stats_users) и
    писавшие боту в личку (bot_contacts).
    Только чтение; без базы бота — пусто."""
    if not enabled():
        return {}
    conn = sqlite3.connect(f"file:{settings.bot_db_path}?mode=ro", uri=True, timeout=15)
    people: dict[int, dict] = {}
    # Сначала чат: имя из Telegram; анкета ниже перезапишет его ФИО.
    # Для каждого источника — запасной запрос, если в базе нет части таблиц.
    queries = [
        # Писали боту в личку — самое слабое имя, зато этим людям бот точно может писать.
        ["SELECT tg_id, full_name, username FROM bot_contacts"],
        ["SELECT user_id, full_name, username FROM stats_users"],
        [
            "SELECT l.tg_id, a.fio, COALESCE(l.username, a.tg_username) FROM activist_links l "
            "LEFT JOIN activists a ON a.id = l.activist_id",
            "SELECT tg_id, NULL, username FROM activist_links",
        ],
    ]
    try:
        for variants in queries:
            rows = []
            for query in variants:
                try:
                    rows = conn.execute(query).fetchall()
                    break
                except sqlite3.OperationalError:  # таблицы нет — в старой базе бота
                    continue
            for tg_id, name, username in rows:
                # Отрицательные id — группы и каналы, им личную рассылку не шлём.
                if not isinstance(tg_id, int) or tg_id <= 0:
                    continue
                person = people.setdefault(tg_id, {"name": None, "username": None})
                if name:
                    person["name"] = name
                if username:
                    person["username"] = str(username).lstrip("@")
        return people
    finally:
        conn.close()


def known_telegram_ids() -> set[int]:
    return set(known_people())
