from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserOut
from app.services import auth_service, editorial_service
from app.services.exceptions import InvalidCredentialsError

router = APIRouter()


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    try:
        access_token = auth_service.login(db, form_data.username, form_data.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def read_current_user(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    current_user.is_editorial_reviewer = editorial_service.is_editor(db, current_user)
    return current_user
