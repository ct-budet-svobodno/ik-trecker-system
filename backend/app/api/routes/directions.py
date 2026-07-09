from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.direction import Direction
from app.models.user import UserRole
from app.repositories import direction_repository
from app.schemas.direction import DirectionHeadsUpdate, DirectionOut
from app.services import direction_service
from app.services.exceptions import UserNotFoundError

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DirectionOut])
def list_directions(db: Session = Depends(get_db)) -> list[Direction]:
    return direction_repository.list_all(db)


@router.put(
    "/{direction_id}/heads",
    response_model=DirectionOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def set_direction_heads(
    direction_id: int,
    payload: DirectionHeadsUpdate,
    db: Session = Depends(get_db),
) -> Direction:
    direction = direction_repository.get_by_id(db, direction_id)
    if direction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Направление не найдено")
    try:
        return direction_service.set_heads(db, direction, payload.user_ids)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
