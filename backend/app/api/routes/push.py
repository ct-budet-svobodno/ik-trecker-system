from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories import push_subscription_repository
from app.schemas.push import (
    PushPublicKeyOut,
    PushSubscriptionCreate,
    PushSubscriptionDelete,
)

router = APIRouter()


@router.get("/public-key", response_model=PushPublicKeyOut)
def get_public_key() -> PushPublicKeyOut:
    if not settings.vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push-уведомления не настроены на сервере",
        )
    return PushPublicKeyOut(public_key=settings.vapid_public_key)


@router.post("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def subscribe(
    payload: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    push_subscription_repository.upsert(
        db,
        user_id=current_user.id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
    )


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    payload: PushSubscriptionDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    sub = push_subscription_repository.get_by_endpoint(db, payload.endpoint)
    if sub is not None and sub.user_id == current_user.id:
        push_subscription_repository.delete_by_endpoint(db, payload.endpoint)
