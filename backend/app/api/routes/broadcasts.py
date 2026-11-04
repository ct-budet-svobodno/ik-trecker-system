from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.broadcast import Broadcast
from app.models.user import User, UserRole
from app.schemas.broadcast import BroadcastIn, BroadcastOut, BroadcastOverview
from app.services import broadcast_service, telegram_service
from app.services.exceptions import BroadcastError

# Рассылка от бота — только админ.
router = APIRouter()
admin_only = require_role(UserRole.ADMIN)


def _out(broadcast: Broadcast) -> dict:
    return {
        "id": broadcast.id,
        "text": broadcast.text,
        "buttons": broadcast.buttons,
        "status": broadcast.status,
        "total": broadcast.total,
        "sent": broadcast.sent,
        "failed": broadcast.failed,
        "author_name": broadcast.author.full_name if broadcast.author else None,
        "created_at": broadcast.created_at,
        "finished_at": broadcast.finished_at,
    }


@router.get("", response_model=BroadcastOverview)
def overview(db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    return {
        "recipients": len(broadcast_service.recipients(db)),
        "enabled": telegram_service.telegram_enabled(),
        "has_telegram": admin.telegram_id is not None,
        "items": [_out(b) for b in broadcast_service.list_recent(db)],
    }


@router.post("/test", status_code=status.HTTP_204_NO_CONTENT)
def send_test(payload: BroadcastIn, admin: User = Depends(admin_only)) -> None:
    try:
        broadcast_service.send_test(admin, payload.text, [b.model_dump(exclude_none=True) for b in payload.buttons])
    except BroadcastError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=BroadcastOut, status_code=status.HTTP_201_CREATED)
def start(payload: BroadcastIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        broadcast = broadcast_service.start(
            db, admin, payload.text, [b.model_dump(exclude_none=True) for b in payload.buttons]
        )
    except BroadcastError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _out(broadcast)


@router.get("/{broadcast_id}", response_model=BroadcastOut)
def get_one(broadcast_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    broadcast = broadcast_service.get(db, broadcast_id)
    if broadcast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рассылка не найдена")
    return _out(broadcast)
