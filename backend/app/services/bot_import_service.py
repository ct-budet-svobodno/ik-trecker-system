"""База бота flood → трекер: каждый активный активист из анкет бота получает
аккаунт в трекере, без второй анкеты и одобрения.

Зачем. Анкеты копились в боте (личка с ботом, импорт из Excel), а трекер
заводил аккаунты только через свою анкету в мини-аппе — половина актива до
трекера не доходила. Обратное направление (трекер → бот) — bot_sync_service.

Как. Человек ищется в трекере по Telegram id, потом по тегу — найден: дописываем
недостающие id и тег, имя и роль не трогаем. Не найден — новый одобренный
аккаунт (логин tg<id> или bot<id анкеты>, пароля нет — вход только из Telegram)
и анкета (ДР, телефон, почта, группа, размер, направление, file_id фото), если
в боте есть дата рождения. Неактивные в боте (ушли) не переносятся.

Когда. import_all — при старте бэкенда и раз в BOT_IMPORT_INTERVAL_MINUTES
(app/main.py), и кнопкой в «Пользователях». import_one — при входе из
мини-аппа, если человек ещё не дошёл до трекера.
"""
import datetime
import logging
import secrets
import sqlite3
import threading
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.direction import Direction
from app.models.user import RegistrationStatus, User, UserRole
from app.models.user_profile import UserProfile
from app.services import bot_sync_service

logger = logging.getLogger(__name__)

# Как направления записаны в анкетах бота руками → короткий код в трекере.
DIRECTION_HINTS = [
    ("цт", "ЦТ"),
    ("цифр", "ЦТ"),
    ("дизайн", "Дизайн"),
    ("фото", "Фото"),
    ("сми", "СМИ"),
    ("прод", "Прод"),
    ("f&u", "Прод"),
]

ACTIVISTS_QUERY = """
SELECT a.id, a.tg_username, a.fio, a.email, a."group", a.phone, a.clothes_size,
       a.someone_div, a.birthday, a.ik_div, l.tg_id
FROM activists a
LEFT JOIN activist_links l ON l.activist_id = a.id
WHERE a.is_active = 1
ORDER BY a.id
"""


def _tag(value: str | None) -> str | None:
    tag = (value or "").strip().lstrip("@")
    return tag or None


def _read_bot() -> tuple[list[dict], dict[int, dict[int, str]]]:
    """Активные анкеты бота и file_id их фото. Только чтение."""
    conn = sqlite3.connect(f"file:{settings.bot_db_path}?mode=ro", uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(ACTIVISTS_QUERY)]
        photos: dict[int, dict[int, str]] = {}
        try:
            for aid, slot, file_id in conn.execute("SELECT activist_id, slot, file_id FROM activist_photos"):
                photos.setdefault(aid, {})[slot] = file_id
        except sqlite3.OperationalError:  # в старой базе бота фото нет
            pass
    finally:
        conn.close()
    # Одна анкета может быть привязана к нескольким Telegram — берём первую строку.
    seen, unique = set(), []
    for row in rows:
        if row["id"] not in seen:
            seen.add(row["id"])
            unique.append(row)
    return unique, photos


def _directions(db: Session, ik_div: str | None) -> list[Direction]:
    """Все упомянутые направления — в порядке упоминания («дизайн, цт» → Дизайн, ЦТ)."""
    text = (ik_div or "").lower()
    found = sorted((text.find(hint), code) for hint, code in DIRECTION_HINTS if hint in text)
    codes = list(dict.fromkeys(code for _, code in found))
    by_code = {d.short_code: d for d in db.scalars(select(Direction).where(Direction.short_code.in_(codes)))}
    return [by_code[c] for c in codes if c in by_code]


def _birthday(value) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _find(db: Session, tg_id: int | None, tag: str | None) -> User | None:
    if tg_id is not None:
        user = db.scalar(select(User).where(User.telegram_id == tg_id))
        if user is not None:
            return user
    if tag:
        return db.scalar(
            select(User)
            .where(func.lower(func.replace(User.telegram_username, "@", "")) == tag.lower())
            .order_by(User.id)
            .limit(1)
        )
    return None


def _username(db: Session, row: dict) -> str:
    base = f"tg{row['tg_id']}" if row["tg_id"] else f"bot{row['id']}"
    name, n = base, 1
    while db.scalar(select(User.id).where(User.username == name)) is not None:
        n += 1
        name = f"{base}_{n}"
    return name


def _apply(db: Session, row: dict, photos: dict[int, str]) -> str:
    """Один активист → трекер. Вернуть, что сделали: created / linked / skipped."""
    tag = _tag(row["tg_username"])
    tg_id = row["tg_id"]
    user = _find(db, tg_id, tag)
    if user is not None:
        changed = False
        # Telegram id не отбираем у другого аккаунта: он уникален.
        if tg_id is not None and user.telegram_id is None and _find(db, tg_id, None) is None:
            user.telegram_id, changed = tg_id, True
        if tag and not user.telegram_username:
            user.telegram_username, changed = tag, True
        # Направления, которых ещё нет, — дописываем; снятые админом не вернём,
        # пока у человека есть хоть одно.
        if not user.directions:
            directions = _directions(db, row["ik_div"])
            if directions:
                user.directions, changed = directions, True
        return "linked" if changed else "skipped"

    fio = " ".join((row["fio"] or "").split())
    if not fio:
        return "skipped"
    user = User(
        username=_username(db, row),
        # Пароля нет: вход только из Telegram.
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        full_name=fio[:128],
        role=UserRole.EMPLOYEE,
        is_active=True,
        registration_status=RegistrationStatus.APPROVED,
        telegram_id=tg_id,
        telegram_username=tag,
    )
    user.is_activist = True
    user.directions = _directions(db, row["ik_div"])
    db.add(user)
    db.flush()
    birthday = _birthday(row["birthday"])
    if birthday is not None:
        db.add(UserProfile(
            user_id=user.id,
            birthday=birthday,
            direction_id=user.directions[0].id if user.directions else None,
            study_group=str(row["group"] or "")[:64],
            phone=str(row["phone"] or "")[:32],
            email=str(row["email"] or "")[:120],
            clothes_size=str(row["clothes_size"] or "")[:16],
            other_units=str(row["someone_div"] or "")[:200],
            # Файлов фото у трекера нет — только file_id из бота.
            photo1="",
            photo2="",
            photo1_file_id=photos.get(1),
            photo2_file_id=photos.get(2),
        ))
    return "created"


def import_all(db: Session) -> dict:
    """Перенести всех. Вернуть отчёт: сколько заведено, привязано, уже было."""
    report = {"created": 0, "linked": 0, "skipped": 0, "names": []}
    if not bot_sync_service.enabled():
        return report
    rows, photos = _read_bot()
    for row in rows:
        result = _apply(db, row, photos.get(row["id"], {}))
        report[result] += 1
        if result == "created":
            report["names"].append(" ".join((row["fio"] or "").split()))
        db.flush()
    db.commit()
    if report["created"] or report["linked"]:
        logger.info("Из бота: заведено %s, привязано %s", report["created"], report["linked"])
    return report


def import_one(db: Session, tg_id: int, username: str | None) -> User | None:
    """Вход из мини-аппа: человек есть в анкетах бота, но не в трекере — заводим сразу."""
    if not bot_sync_service.enabled():
        return None
    tag = _tag(username)
    rows, photos = _read_bot()
    row = next((r for r in rows if r["tg_id"] == tg_id), None)
    if row is None and tag:
        row = next((r for r in rows if _tag(r["tg_username"]) and _tag(r["tg_username"]).lower() == tag.lower()), None)
    if row is None:
        return None
    # Вошёл из Telegram — значит, этот id точно его, даже если в боте не привязан.
    row = {**row, "tg_id": tg_id, "tg_username": row["tg_username"] or tag}
    _apply(db, row, photos.get(row["id"], {}))
    db.commit()
    return db.scalar(select(User).where(User.telegram_id == tg_id))


# ── Фоновая синхронизация ──

def _loop(interval: float) -> None:
    while True:
        db = SessionLocal()
        try:
            import_all(db)
        except Exception:
            logger.exception("Импорт из бота не удался")
        finally:
            db.close()
        time.sleep(interval)


def start_background() -> None:
    minutes = settings.bot_import_interval_minutes
    if minutes <= 0 or not settings.bot_db_path:
        return
    threading.Thread(target=_loop, args=(minutes * 60,), daemon=True).start()
