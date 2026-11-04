import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    RegistrationOptions,
    TelegramClaim,
    TelegramConfig,
    TelegramInitData,
    TelegramLinkCode,
    Token,
)
from app.schemas.user import UserOut
from app.services import auth_service, editorial_service, registration_service, telegram_service
from app.services.exceptions import (
    InvalidCredentialsError,
    LinkCodeError,
    RegistrationError,
    RegistrationPendingError,
    TelegramAuthError,
    TelegramNotLinkedError,
)

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


@router.get("/telegram/config", response_model=TelegramConfig)
def telegram_config() -> TelegramConfig:
    return TelegramConfig(
        enabled=telegram_service.telegram_enabled(),
        bot_username=telegram_service.bot_username(),
    )


@router.post("/telegram", response_model=Token)
def login_with_telegram(payload: TelegramInitData, db: Session = Depends(get_db)) -> Token:
    try:
        access_token = auth_service.login_with_telegram(db, payload.init_data)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except TelegramNotLinkedError as exc:
        # Фронт по 404 показывает анкету (registration_service.register).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RegistrationPendingError as exc:
        # Анкета есть, но админ не одобрил: фронт показывает «на рассмотрении».
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": f"registration_{exc.status}", "message": str(exc)},
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return Token(access_token=access_token)


@router.post("/telegram/link", response_model=UserOut)
def link_telegram(
    payload: TelegramInitData,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    try:
        user = auth_service.link_telegram(db, current_user, payload.init_data)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    user.is_editorial_reviewer = editorial_service.is_editor(db, user)
    return user


@router.delete("/telegram/link", response_model=UserOut)
def unlink_telegram(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    user = auth_service.unlink_telegram(db, current_user)
    user.is_editorial_reviewer = editorial_service.is_editor(db, user)
    return user


# ── Анкета из мини-аппа и привязка по коду (registration_service) ──

@router.get("/telegram/registration-options", response_model=RegistrationOptions)
def registration_options(db: Session = Depends(get_db)) -> dict:
    return registration_service.options(db)


@router.post("/telegram/register", status_code=status.HTTP_201_CREATED)
async def register_with_telegram(
    init_data: str = Form(..., max_length=8192),
    full_name: str = Form(..., max_length=200),
    birthday: datetime.date = Form(...),
    direction_id: int | None = Form(None),
    study_group: str = Form(..., max_length=200),
    phone: str = Form(..., max_length=64),
    email: str = Form(..., max_length=200),
    clothes_size: str = Form(..., max_length=16),
    other_units: str = Form("", max_length=400),
    photo1: UploadFile = File(...),
    photo2: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    photos = [
        await photo.read(registration_service.MAX_PHOTO_BYTES + 1) for photo in (photo1, photo2)
    ]
    try:
        registration_service.register(
            db,
            init_data,
            full_name=full_name,
            birthday=birthday,
            direction_id=direction_id,
            study_group=study_group,
            phone=phone,
            email=email,
            clothes_size=clothes_size,
            other_units=other_units,
            photos=photos,
        )
    except TelegramAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except RegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"status": "pending"}


@router.post("/telegram/link-code", response_model=TelegramLinkCode)
def create_link_code(current_user: User = Depends(get_current_user)) -> TelegramLinkCode:
    """Для веб-версии: ссылка в мини-апп, которая привяжет Telegram к этому аккаунту."""
    code, url = registration_service.create_link_code(current_user)
    return TelegramLinkCode(code=code, url=url)


@router.post("/telegram/claim", response_model=Token)
def claim_link_code(payload: TelegramClaim, db: Session = Depends(get_db)) -> Token:
    try:
        access_token = registration_service.claim_link_code(db, payload.init_data, payload.code)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except LinkCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return Token(access_token=access_token)
