import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.editorial_post import EditorialCommentTarget, EditorialStatus


class EditorialUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    username: str


class EditorialCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    target: EditorialCommentTarget
    body: str
    parent_id: int | None
    resolved: bool
    author_id: int
    author: EditorialUser
    created_at: datetime.datetime


class EditorialPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime.date
    title: str
    format: str | None
    brief: str
    reference: str | None
    writer_id: int | None
    writer: EditorialUser | None
    designer_id: int | None
    designer: EditorialUser | None
    editor_id: int | None
    editor: EditorialUser | None
    text_content: str
    text_status: EditorialStatus
    figma_url: str | None
    design_done: bool
    design_status: EditorialStatus
    created_by_id: int
    created_at: datetime.datetime


class EditorialPostDetailOut(EditorialPostOut):
    comments: list[EditorialCommentOut] = []


class EditorialPostCreate(BaseModel):
    date: datetime.date
    title: str = Field(min_length=1, max_length=200)
    format: str | None = Field(default=None, max_length=100)
    brief: str = ""
    reference: str | None = Field(default=None, max_length=500)


class EditorialPostUpdate(BaseModel):
    # Все поля опциональны; права проверяются пофилдно по model_fields_set.
    title: str | None = Field(default=None, min_length=1, max_length=200)
    date: datetime.date | None = None
    format: str | None = Field(default=None, max_length=100)
    brief: str | None = None
    reference: str | None = Field(default=None, max_length=500)
    text_content: str | None = None
    text_status: EditorialStatus | None = None
    figma_url: str | None = Field(default=None, max_length=500)
    design_done: bool | None = None
    design_status: EditorialStatus | None = None


class EditorialAssignRequest(BaseModel):
    role: Literal["writer", "designer", "editor"]
    # Без user_id — проставляется текущий пользователь («стать райтером»).
    user_id: int | None = None


class EditorialCommentCreate(BaseModel):
    target: EditorialCommentTarget
    body: str = Field(min_length=1, max_length=4000)
    parent_id: int | None = None


class EditorialCommentUpdate(BaseModel):
    resolved: bool
