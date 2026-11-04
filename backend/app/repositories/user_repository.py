from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_by_telegram_id(db: Session, telegram_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == telegram_id))


def find_unlinked_by_tag(db: Session, tag: str) -> User | None:
    """Аккаунт с этим Telegram-тегом, но без привязанного Telegram id."""
    return db.scalar(
        select(User)
        .where(
            User.telegram_id.is_(None),
            func.lower(func.replace(User.telegram_username, "@", "")) == tag.lower(),
        )
        .order_by(User.id)
        .limit(1)
    )


def find_by_telegram_tags(db: Session, tags: list[str]) -> dict[str, User]:
    """Активные пользователи по Telegram-тегам (без «@», без учёта регистра)."""
    wanted = {t.lower() for t in tags}
    if not wanted:
        return {}
    users = db.scalars(
        select(User).where(
            User.is_active.is_(True),
            func.lower(func.replace(User.telegram_username, "@", "")).in_(wanted),
        )
    )
    return {u.telegram_username.lstrip("@").lower(): u for u in users}


def list_all(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def create(db: Session, *, username: str, hashed_password: str, full_name: str, role: UserRole) -> User:
    user = User(
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update(db: Session, user: User, **fields) -> User:
    for key, value in fields.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def set_telegram(db: Session, user: User, *, telegram_id: int | None, username: str | None) -> User:
    # update() пропускает None, а здесь None — это «отвязать».
    user.telegram_id = telegram_id
    user.telegram_username = username
    db.commit()
    db.refresh(user)
    return user
