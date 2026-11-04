from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.core.telegram import InvalidInitDataError, validate_init_data
from app.models.user import RegistrationStatus, User
from app.repositories import user_repository
from app.services import bot_import_service
from app.services.exceptions import (
    InvalidCredentialsError,
    RegistrationPendingError,
    TelegramAuthError,
    TelegramNotLinkedError,
)


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = user_repository.get_by_username(db, username)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Неверный логин или пароль")
    if not user.is_active:
        raise InvalidCredentialsError("Учётная запись деактивирована")
    return user


def login(db: Session, username: str, password: str) -> str:
    user = authenticate_user(db, username, password)
    return create_access_token(subject=user.username, role=user.role.value)


def telegram_user(init_data: str) -> dict:
    """Проверенный пользователь Telegram из initData мини-аппа."""
    try:
        return validate_init_data(
            init_data, settings.telegram_bot_token, settings.telegram_auth_max_age
        )
    except InvalidInitDataError as exc:
        raise TelegramAuthError(str(exc)) from exc


def login_with_telegram(db: Session, init_data: str) -> str:
    """Вход из мини-аппа: Telegram-аккаунт уже привязан — пароль не нужен."""
    tg_user = telegram_user(init_data)
    user = user_repository.get_by_telegram_id(db, tg_user["id"])
    if user is None:
        user = _match_existing(db, tg_user)
    if user is None:
        raise TelegramNotLinkedError("Telegram ещё не привязан: заполните анкету")
    if user.registration_status == RegistrationStatus.PENDING:
        raise RegistrationPendingError("pending", "Анкета на рассмотрении у админа")
    if user.registration_status == RegistrationStatus.REJECTED:
        raise RegistrationPendingError("rejected", "Заявку не одобрили")
    if not user.is_active:
        raise InvalidCredentialsError("Учётная запись деактивирована")
    return create_access_token(subject=user.username, role=user.role.value)


def _match_existing(db: Session, tg_user: dict) -> User | None:
    """Человек уже есть, но Telegram не привязан: аккаунт с тем же тегом (тег
    подтверждает сама подпись Telegram) или анкета в базе бота — без второй анкеты."""
    tag = (tg_user.get("username") or "").strip().lstrip("@")
    if tag:
        user = user_repository.find_unlinked_by_tag(db, tag)
        if user is not None:
            return user_repository.set_telegram(db, user, telegram_id=tg_user["id"], username=tag)
    return bot_import_service.import_one(db, tg_user["id"], tag or None)


def link_telegram(db: Session, user: User, init_data: str) -> User:
    """Привязать Telegram, из которого открыт мини-апп, к вошедшему пользователю.
    Если этот Telegram был привязан к другому аккаунту — переносим: подпись
    Telegram доказывает, что аккаунт в руках того, кто сейчас вошёл."""
    tg_user = telegram_user(init_data)
    previous = user_repository.get_by_telegram_id(db, tg_user["id"])
    if previous is not None and previous.id != user.id:
        user_repository.set_telegram(db, previous, telegram_id=None, username=None)
    return user_repository.set_telegram(
        db, user, telegram_id=tg_user["id"], username=tg_user.get("username")
    )


def unlink_telegram(db: Session, user: User) -> User:
    return user_repository.set_telegram(db, user, telegram_id=None, username=None)
