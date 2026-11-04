from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.direction import Direction
from app.models.user import LeadershipPosition, User, UserRole
from app.models.user_profile import UserProfile
from app.repositories import user_repository
from app.schemas.user import UserCreate
from app.services.exceptions import RegistrationError, UsernameTakenError


def create_user(db: Session, user_create: UserCreate) -> User:
    if user_repository.get_by_username(db, user_create.username) is not None:
        raise UsernameTakenError(f"Логин '{user_create.username}' уже занят")
    return user_repository.create(
        db,
        username=user_create.username,
        hashed_password=hash_password(user_create.password),
        full_name=user_create.full_name,
        role=user_create.role,
    )


def list_users(db: Session) -> list[User]:
    return user_repository.list_all(db)


def set_role(db: Session, user: User, role: UserRole) -> User:
    return user_repository.update(db, user, role=role)


def set_active(db: Session, user: User, is_active: bool) -> User:
    return user_repository.update(db, user, is_active=is_active)


def set_directions(db: Session, user: User, direction_ids: list[int]) -> User:
    """Направления участника. В анкете направление одно (её читают бот и заявки):
    если там уже не его направление — ставим первое из новых."""
    directions = []
    for direction_id in dict.fromkeys(direction_ids):
        direction = db.get(Direction, direction_id)
        if direction is None:
            raise RegistrationError("Такого направления нет")
        directions.append(direction)
    user.directions = directions
    profile = db.get(UserProfile, user.id)
    if profile is not None and profile.direction_id not in direction_ids:
        profile.direction_id = directions[0].id if directions else None
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user: User, raw_password: str) -> User:
    return user_repository.update(db, user, hashed_password=hash_password(raw_password))


def set_leadership_position(
    db: Session, user: User, position: LeadershipPosition | None
) -> User:
    """Назначить/снять должность «тройки». Должность единоличная — снимаем её
    с прежнего держателя, чтобы Председатель/Секретарь/Первый зам был один."""
    if position is not None:
        for other in user_repository.list_all(db):
            if other.id != user.id and other.leadership_position == position:
                other.leadership_position = None
        # Член тройки должен иметь доступ к разделам руководства — минимум manager.
        if user.role == UserRole.EMPLOYEE:
            user.role = UserRole.MANAGER
    user.leadership_position = position
    db.commit()
    db.refresh(user)
    return user
