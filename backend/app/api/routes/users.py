from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories import user_repository
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import editorial_service, user_service
from app.services.exceptions import UsernameTakenError

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
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))],
)
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return [_with_reviewer_flag(db, user) for user in user_service.list_users(db)]


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
    if user_update.password:
        user_service.set_password(db, user, user_update.password)
    user = user_repository.update(
        db,
        user,
        full_name=user_update.full_name,
        role=user_update.role,
        is_active=user_update.is_active,
        is_editorial=user_update.is_editorial,
        is_zavod=user_update.is_zavod,
    )
    return _with_reviewer_flag(db, user)
