import datetime

from pydantic import BaseModel, Field

from app.models.checklist import ChecklistStatus


class ChecklistPrepare(BaseModel):
    facts: list[str] = Field(min_length=3, max_length=500)


class ChecklistCardOut(BaseModel):
    id: int
    number: int
    tg_id: int
    full_name: str
    username: str | None
    facts: list[str]
    image_ready: bool
    status: ChecklistStatus
    sent_at: datetime.datetime | None
    photos: list[bool]  # какие из трёх фото уже прислал


class ChecklistOverview(BaseModel):
    default_facts: list[str]
    cards: list[ChecklistCardOut]
    people: int  # скольким раздадим, если подготовить сейчас
    sending: bool
    enabled: bool  # бот подключён и база бота доступна


class ChecklistByTag(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class ChecklistTagCard(BaseModel):
    card: ChecklistCardOut
    needs_image: bool  # новый лист — админка рисует картинку и загружает
