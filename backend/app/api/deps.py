import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories import user_repository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise credentials_error

    username = payload.get("sub")
    if username is None:
        raise credentials_error

    user = user_repository.get_by_username(db, username)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_zavod(current_user: User = Depends(get_current_user)) -> User:
    """Доступ к ZAVOD: личный флаг, админ или должность руководства.
    Зеркало геттера isZavod на фронте — держать эти два места в согласии."""
    if (
        current_user.role != UserRole.ADMIN
        and current_user.leadership_position is None
        and not current_user.is_zavod
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к ZAVOD",
        )
    return current_user


def require_role(*roles: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для этого действия",
            )
        return current_user

    return dependency
