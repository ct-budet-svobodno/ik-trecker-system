from sqlalchemy.orm import Session

from app.models.direction import Direction
from app.models.user import User, UserRole
from app.repositories import direction_repository, user_repository
from app.services.exceptions import UserNotFoundError


def list_directions(db: Session) -> list[Direction]:
    return direction_repository.list_all(db)


def set_heads(db: Session, direction: Direction, user_ids: list[int]) -> Direction:
    # Убираем дубликаты, сохраняя порядок.
    unique_ids = list(dict.fromkeys(user_ids))

    heads: list[User] = []
    for user_id in unique_ids:
        user = user_repository.get_by_id(db, user_id)
        if user is None:
            raise UserNotFoundError(f"Пользователь с id={user_id} не найден")
        # Руководитель направления должен видеть все задачи — это роль manager.
        # Рядового сотрудника при назначении повышаем до руководителя.
        if user.role == UserRole.EMPLOYEE:
            user.role = UserRole.MANAGER
        heads.append(user)

    return direction_repository.set_heads(db, direction, heads)
