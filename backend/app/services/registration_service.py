"""Вход в мини-апп без логина и пароля.

Человек открывает трекер из Telegram. Если его Telegram ни к кому не привязан,
вместо экрана входа — анкета (ФИО, день рождения, направление, группа,
телефон, почта, размер одежды, два фото). Заполнил — создаётся аккаунт со
статусом PENDING (is_active=False: войти и получать задачи нельзя), админам
приходит уведомление, анкета с фото уходит в группу-архив. Админ одобряет —
аккаунт активен, человек входит в мини-апп сразу; отклоняет — REJECTED.

Уже заведённые аккаунты без Telegram привязываются кодом: в веб-версии
«Подключить Telegram» выдаёт ссылку t.me/<бот>?startapp=link_<код>, мини-апп
по ней вызывает claim — и второй аккаунт не появляется.
"""
import datetime
import html
import logging
import re
import secrets
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.direction import Direction
from app.models.user import RegistrationStatus, User, UserRole
from app.models.user_profile import UserProfile
from app.repositories import user_repository
from app.db.session import SessionLocal
from app.services import auth_service, bot_sync_service, push_service, telegram_service
from app.services.exceptions import LinkCodeError, RegistrationError

logger = logging.getLogger(__name__)

CLOTHES_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
MAX_PHOTO_BYTES = 8 * 1024 * 1024
# Сигнатуры форматов, которые принимаем (фронт и так ужимает в JPEG).
IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"RIFF")
LINK_CODE_TTL = 15 * 60
LINK_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def options(db: Session) -> dict:
    directions = db.scalars(select(Direction).order_by(Direction.sort_order, Direction.id))
    return {
        "directions": [{"id": d.id, "name": d.name} for d in directions],
        "clothes_sizes": CLOTHES_SIZES,
    }


# ── Проверка полей анкеты ──

def _phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) != 11 or digits[0] != "7":
        raise RegistrationError("Не похоже на номер телефона. Формат: +7 999 123-45-67")
    return digits


def _email(raw: str) -> str:
    value = raw.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", value) or len(value) > 120:
        raise RegistrationError("Не похоже на почту. Например: ivanov@urfu.me")
    return value


def _full_name(raw: str) -> str:
    value = " ".join(raw.split())
    if len(value.split()) < 2 or len(value) > 120:
        raise RegistrationError("Нужно ФИО: хотя бы фамилия и имя")
    if not re.fullmatch(r"[А-Яа-яЁёA-Za-z\s\-']+", value):
        raise RegistrationError("В ФИО только буквы, дефис и пробелы")
    return value


def _birthday(value: datetime.date) -> datetime.date:
    if not 1950 <= value.year <= datetime.date.today().year - 10:
        raise RegistrationError("Проверьте дату рождения")
    return value


def _required(raw: str, label: str, limit: int) -> str:
    value = " ".join(raw.split())
    if not value:
        raise RegistrationError(f"Заполните поле «{label}»")
    if len(value) > limit:
        raise RegistrationError(f"Слишком длинно: «{label}»")
    return value


def _size(value: str) -> str:
    if value not in CLOTHES_SIZES:
        raise RegistrationError("Выберите размер одежды")
    return value


def _check_photo(data: bytes) -> bytes:
    if not data:
        raise RegistrationError("Нужны два фото")
    if len(data) > MAX_PHOTO_BYTES:
        raise RegistrationError("Фото слишком большое (больше 8 МБ)")
    if not data.startswith(IMAGE_MAGIC):
        raise RegistrationError("Фото должно быть картинкой (JPEG, PNG или WebP)")
    return data


def _photos_dir() -> Path:
    path = Path(settings.profile_photos_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def photo_path(name: str) -> Path:
    return _photos_dir() / name


# ── Анкета ──

def register(
    db: Session,
    init_data: str,
    *,
    full_name: str,
    birthday: datetime.date,
    direction_id: int | None,
    study_group: str,
    phone: str,
    email: str,
    clothes_size: str,
    other_units: str,
    photos: list[bytes],
) -> User:
    tg_user = auth_service.telegram_user(init_data)
    full_name = _full_name(full_name)
    profile_fields = {
        "birthday": _birthday(birthday),
        "direction_id": direction_id,
        "study_group": _required(study_group, "Группа", 64),
        "phone": _phone(phone),
        "email": _email(email),
        "clothes_size": _size(clothes_size),
        "other_units": " ".join(other_units.split())[:200],
    }
    if direction_id is not None and db.get(Direction, direction_id) is None:
        raise RegistrationError("Такого направления нет")
    if len(photos) != 2:
        raise RegistrationError("Нужны два фото")
    photos = [_check_photo(p) for p in photos]

    user = user_repository.get_by_telegram_id(db, tg_user["id"])
    if user is not None and user.registration_status == RegistrationStatus.APPROVED:
        raise RegistrationError("Аккаунт уже есть — откройте трекер заново")
    if user is None:
        user = User(
            username=f"tg{tg_user['id']}",
            # Пароля у такого аккаунта нет: вход только из Telegram.
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name=full_name,
            role=UserRole.EMPLOYEE,
            is_active=False,
            telegram_id=tg_user["id"],
        )
        db.add(user)
    # Отклонённую заявку можно подать заново — снова на рассмотрение.
    user.full_name = full_name
    user.telegram_username = tg_user.get("username")
    user.registration_status = RegistrationStatus.PENDING
    user.is_active = False
    db.flush()

    names = []
    for slot, data in enumerate(photos, start=1):
        name = f"user{user.id}_{slot}_{secrets.token_hex(4)}.jpg"
        photo_path(name).write_bytes(data)
        names.append(name)
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    else:
        for old in (profile.photo1, profile.photo2):
            photo_path(old).unlink(missing_ok=True)
    for key, value in profile_fields.items():
        setattr(profile, key, value)
    profile.photo1, profile.photo2 = names
    user.directions = [db.get(Direction, direction_id)] if direction_id is not None else []
    profile.submitted_at = datetime.datetime.now(datetime.UTC)
    db.commit()
    db.refresh(user)

    _notify_admins(db, user)
    _send_to_archive(db, user, profile, photos)
    return user


def _notify_admins(db: Session, user: User) -> None:
    admins = [u.id for u in user_repository.list_all(db) if u.role == UserRole.ADMIN and u.is_active]
    push_service.send_to_users(
        db, admins, title="Новая заявка в трекер", body=user.full_name, url="/users"
    )


def _send_to_archive(db: Session, user: User, profile: UserProfile, photos: list[bytes]) -> None:
    chat_id = settings.telegram_anketa_chat_id
    if chat_id is None:
        return
    direction = db.get(Direction, profile.direction_id) if profile.direction_id else None
    esc = html.escape
    tag = f"@{user.telegram_username}" if user.telegram_username else "без тега"
    lines = [
        "🆕 <b>Анкета из трекера</b>",
        f"👤 <b>ФИО:</b> {esc(user.full_name)}",
        f"🎂 <b>День рождения:</b> {profile.birthday:%d.%m.%Y}",
        f"🧭 <b>Направление:</b> {esc(direction.name) if direction else '—'}",
        f"🎓 <b>Группа:</b> {esc(profile.study_group)}",
        f"📞 <b>Телефон:</b> +{profile.phone}",
        f"✉️ <b>Почта:</b> {esc(profile.email)}",
        f"👕 <b>Размер:</b> {esc(profile.clothes_size)}",
        f"🏢 <b>Другие подразделения:</b> {esc(profile.other_units) or '—'}",
        f'💬 <b>Telegram:</b> <a href="tg://user?id={user.telegram_id}">{esc(tag)}</a>',
    ]
    user_id = user.id

    def remember_file_ids(file_ids: list[str]) -> None:
        # Отдельная сессия: вызывается из фонового потока после ответа Telegram.
        if len(file_ids) != 2:
            return
        with SessionLocal() as session:
            saved = session.get(UserProfile, user_id)
            if saved is not None:
                saved.photo1_file_id, saved.photo2_file_id = file_ids
                session.commit()

    telegram_service.send_album(chat_id, photos, "\n".join(lines), on_sent=remember_file_ids)


# ── Решение админа ──

def list_pending(db: Session) -> list[User]:
    query = (
        select(User)
        .where(User.registration_status == RegistrationStatus.PENDING)
        .order_by(User.id)
    )
    return list(db.scalars(query))


def profile_of(db: Session, user: User) -> UserProfile | None:
    return db.get(UserProfile, user.id)


def approve(db: Session, user: User) -> User:
    if user.registration_status != RegistrationStatus.PENDING:
        raise RegistrationError("Заявка уже рассмотрена")
    user.registration_status = RegistrationStatus.APPROVED
    user.is_active = True
    user.is_activist = True
    db.commit()
    db.refresh(user)
    _sync_to_bot(db, user)
    if user.telegram_id is not None:
        telegram_service.send_message(
            user.telegram_id,
            "✅ <b>Доступ к трекеру ИК открыт</b>\nЗаходи — задачи, календарь и игры уже ждут.",
            [telegram_service.webapp_button("Открыть трекер", "/")],
        )
    return user


def _sync_to_bot(db: Session, user: User) -> None:
    """Анкету — в базу бота (для !инфо). Сбой не отменяет одобрение: доступ к
    трекеру важнее, а записать в бот можно повторным одобрением после починки."""
    profile = db.get(UserProfile, user.id)
    if profile is None:
        return
    direction = db.get(Direction, profile.direction_id) if profile.direction_id else None
    try:
        bot_sync_service.sync_profile(user, profile, direction.short_code if direction else None)
    except Exception:
        logger.exception("Анкета %s не записалась в базу бота", user.id)


def reject(db: Session, user: User) -> User:
    if user.registration_status != RegistrationStatus.PENDING:
        raise RegistrationError("Заявка уже рассмотрена")
    user.registration_status = RegistrationStatus.REJECTED
    user.is_active = False
    db.commit()
    db.refresh(user)
    if user.telegram_id is not None:
        telegram_service.send_message(
            user.telegram_id,
            "Заявку в трекер ИК пока не одобрили. Если это ошибка — напиши руководству.",
        )
    return user


# ── Привязка существующего аккаунта по коду ──

# Код живёт 15 минут в памяти процесса: перезапуск их сбросит — просто
# нажать «Подключить Telegram» ещё раз.
_link_codes: dict[str, tuple[int, float]] = {}


def create_link_code(user: User) -> tuple[str, str | None]:
    now = time.monotonic()
    for code, (_, expires) in list(_link_codes.items()):
        if expires < now:
            del _link_codes[code]
    code = "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(10))
    _link_codes[code] = (user.id, now + LINK_CODE_TTL)
    return code, telegram_service.startapp_url(f"link_{code}")


def claim_link_code(db: Session, init_data: str, code: str) -> str:
    """Привязать Telegram мини-аппа к аккаунту, выдавшему код, и войти."""
    entry = _link_codes.pop(code.upper(), None)
    if entry is None or entry[1] < time.monotonic():
        raise LinkCodeError("Ссылка устарела — нажмите «Подключить Telegram» в трекере ещё раз")
    user = user_repository.get_by_id(db, entry[0])
    if user is None or not user.is_active:
        raise LinkCodeError("Аккаунт не найден или отключён")
    tg_user = auth_service.telegram_user(init_data)
    # Если этот Telegram успел подать анкету — та заявка больше не нужна.
    duplicate = user_repository.get_by_telegram_id(db, tg_user["id"])
    if (
        duplicate is not None
        and duplicate.id != user.id
        and duplicate.registration_status != RegistrationStatus.APPROVED
    ):
        profile = db.get(UserProfile, duplicate.id)
        if profile is not None:
            for name in (profile.photo1, profile.photo2):
                photo_path(name).unlink(missing_ok=True)
            db.delete(profile)
        db.delete(duplicate)
        db.commit()
    auth_service.link_telegram(db, user, init_data)
    return create_access_token(subject=user.username, role=user.role.value)
