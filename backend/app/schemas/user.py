from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import LeadershipPosition, UserRole


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
    # Вычисляется в роутах: True для админа и руководителей СМИ/Дизайна.
    # Нужно фронту, чтобы показать вкладку «Редакция» ревьюерам без личного флага.
    is_editorial_reviewer: bool = False
    created_at: datetime
