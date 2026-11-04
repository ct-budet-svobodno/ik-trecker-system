from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import LeadershipPosition, RegistrationStatus, UserRole


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=128)
    role: UserRole = UserRole.EMPLOYEE


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None
    # Должность «тройки». Передаётся явно (вкл. null для снятия) — см. update_user.
    leadership_position: LeadershipPosition | None = None
    # Участник Редакции (передаётся при изменении).
    is_editorial: bool | None = None
    # Доступ к разделу ZAVOD (передаётся при изменении).
    is_zavod: bool | None = None
    # В активе (передаётся при изменении).
    is_activist: bool | None = None
    # Направления участника (передаётся при изменении, [] — снять все).
    direction_ids: list[int] | None = None
    # Сброс пароля админом (необязательно).
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: UserRole
    leadership_position: LeadershipPosition | None = None
    is_active: bool
    is_editorial: bool = False
    is_zavod: bool = False
    is_activist: bool = False
    direction_ids: list[int] = []
    # Вычисляется в роутах: True для админа и руководителей СМИ/Дизайна.
    # Нужно фронту, чтобы показать вкладку «Редакция» ревьюерам без личного флага.
    is_editorial_reviewer: bool = False
    telegram_username: str | None = None
    telegram_linked: bool = False
    created_at: datetime


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    birthday: date
    direction_id: int | None
    direction_name: str | None = None
    study_group: str
    phone: str
    email: str
    clothes_size: str
    other_units: str
    submitted_at: datetime


class RegistrationOut(BaseModel):
    """Заявка из мини-аппа для админа."""

    id: int
    full_name: str
    telegram_username: str | None
    registration_status: RegistrationStatus
    profile: UserProfileOut | None


class BotImportOut(BaseModel):
    created: int  # заведены новые аккаунты
    linked: int  # у уже имевшихся дописаны Telegram id или тег
    skipped: int  # уже были, менять нечего
    names: list[str]  # кого завели
