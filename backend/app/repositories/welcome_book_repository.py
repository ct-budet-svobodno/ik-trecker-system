from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.models.user import RegistrationStatus, User
from app.models.welcome_book import WelcomeBookProgress


def record(db: Session, user_id: int, version: str, page: int) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    query = insert(WelcomeBookProgress).values(
        user_id=user_id, version=version, max_page=page,
        first_opened_at=now, last_seen_at=now,
    )
    # Две вкладки и запоздалые запросы не уменьшают достигнутый прогресс.
    db.execute(query.on_conflict_do_update(
        index_elements=["user_id", "version"],
        set_={
            "max_page": func.max(WelcomeBookProgress.max_page, query.excluded.max_page),
            "last_seen_at": func.max(WelcomeBookProgress.last_seen_at, query.excluded.last_seen_at),
        },
    ))
    db.commit()


def list_readers(db: Session, version: str):
    return db.execute(
        select(User, WelcomeBookProgress)
        .outerjoin(WelcomeBookProgress, and_(
            WelcomeBookProgress.user_id == User.id,
            WelcomeBookProgress.version == version,
        ))
        .where(User.is_active.is_(True), User.registration_status == RegistrationStatus.APPROVED)
        .order_by(User.full_name, User.id)
    ).all()
