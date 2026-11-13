from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories import user_repository
from app.models.user import RegistrationStatus
from app.schemas.user import BotImportOut, ChecklistAssigneeOut, RegistrationOut, UserCreate, UserOut, UserProfileOut, UserUpdate
from app.services import bot_import_service, editorial_service, registration_service, user_service
from app.services.exceptions import RegistrationError, UsernameTakenError

router = APIRouter()


def _with_reviewer_flag(db: Session, user: User) -> User:
    """Проставляет вычисляемый is_editorial_reviewer на объект (для UserOut)."""
    user.is_editorial_reviewer = editorial_service.is_editor(db, user)
    return user


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def create_user(user_create: UserCreate, db: Session = Depends(get_db)) -> User:
    try:
        return user_service.create_user(db, user_create)
    except UsernameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "",
    response_model=list[UserOut],
)
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[User]:
    if current_user.role == UserRole.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    # Заявки из мини-аппа (ещё не одобренные) сюда не попадают — они в /registrations.
    return [
        _with_reviewer_flag(db, user)
        for user in user_service.list_users(db)
        if user.registration_status == RegistrationStatus.APPROVED
    ]


@router.get("/checklist-assignees", response_model=list[ChecklistAssigneeOut])
def list_checklist_assignees(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[User]:
    return [
        user for user in user_service.list_users(db)
        if user.is_active and user.registration_status == RegistrationStatus.APPROVED
    ]


# ── Заявки из мини-аппа ──

def _registration(db: Session, user: User) -> dict:
    profile = registration_service.profile_of(db, user)
    profile_out = None
    if profile is not None:
        profile_out = UserProfileOut.model_validate(profile)
        profile_out.direction_name = profile.direction.name if profile.direction else None
    return {
        "id": user.id,
        "full_name": user.full_name,
        "telegram_username": user.telegram_username,
        "registration_status": user.registration_status,
        "profile": profile_out,
    }


def _pending_user(db: Session, user_id: int) -> User:
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


@router.get(
    "/registrations",
    response_model=list[RegistrationOut],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def list_registrations(db: Session = Depends(get_db)) -> list[dict]:
    return [_registration(db, user) for user in registration_service.list_pending(db)]


@router.post(
    "/import-from-bot",
    response_model=BotImportOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def import_from_bot(db: Session = Depends(get_db)) -> dict:
    """Подтянуть анкеты из бота: кого нет в трекере — завести (обычно это
    делает фоновая синхронизация раз в 10 минут)."""
    return bot_import_service.import_all(db)


@router.post(
    "/{user_id}/approve",
    response_model=RegistrationOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def approve_registration(user_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        user = registration_service.approve(db, _pending_user(db, user_id))
    except RegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _registration(db, user)


@router.post(
    "/{user_id}/reject",
    response_model=RegistrationOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def reject_registration(user_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        user = registration_service.reject(db, _pending_user(db, user_id))
    except RegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _registration(db, user)


@router.get(
    "/{user_id}/photo/{slot}",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def profile_photo(user_id: int, slot: int, db: Session = Depends(get_db)) -> FileResponse:
    profile = registration_service.profile_of(db, _pending_user(db, user_id))
    if profile is None or slot not in (1, 2):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фото нет")
    path = registration_service.photo_path(profile.photo1 if slot == 1 else profile.photo2)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фото нет")
    return FileResponse(path, media_type="image/jpeg")


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)) -> User:
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    # leadership_position обрабатываем отдельно: должность единоличная и может
    # явно сниматься (null), поэтому смотрим, передано ли поле вообще.
    if "leadership_position" in user_update.model_fields_set:
        user_service.set_leadership_position(db, user, user_update.leadership_position)
    if user_update.direction_ids is not None:
        try:
            user_service.set_directions(db, user, user_update.direction_ids)
        except RegistrationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if user_update.password:
        user_service.set_password(db, user, user_update.password)
    # Держатель должности руководства — минимум manager: форма шлёт роль вместе
    # с должностью, и employee затёр бы повышение из set_leadership_position.
    role = user_update.role
    if user.leadership_position is not None and role == UserRole.EMPLOYEE:
        role = UserRole.MANAGER
    user = user_repository.update(
        db,
        user,
        full_name=user_update.full_name,
        role=role,
        is_active=user_update.is_active,
        is_editorial=user_update.is_editorial,
        is_zavod=user_update.is_zavod,
        is_activist=user_update.is_activist,
    )
    return _with_reviewer_flag(db, user)
