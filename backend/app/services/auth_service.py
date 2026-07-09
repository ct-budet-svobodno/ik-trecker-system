from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories import user_repository
from app.services.exceptions import InvalidCredentialsError


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
