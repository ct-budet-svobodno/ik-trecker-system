from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.push_subscription import PushSubscription


def list_for_user(db: Session, user_id: int) -> list[PushSubscription]:
    return list(
        db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id))
    )


def get_by_endpoint(db: Session, endpoint: str) -> PushSubscription | None:
    return db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))


def upsert(db: Session, *, user_id: int, endpoint: str, p256dh: str, auth: str) -> PushSubscription:
    sub = get_by_endpoint(db, endpoint)
    if sub is None:
        sub = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.add(sub)
    else:
        # Подписка могла перейти к другому пользователю на том же устройстве.
        sub.user_id = user_id
        sub.p256dh = p256dh
        sub.auth = auth
    db.commit()
    db.refresh(sub)
    return sub


def delete_by_endpoint(db: Session, endpoint: str) -> None:
    sub = get_by_endpoint(db, endpoint)
    if sub is not None:
        db.delete(sub)
        db.commit()
