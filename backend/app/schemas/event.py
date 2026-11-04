from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _wall_clock(value: datetime | None) -> datetime | None:
    """Время мероприятия — «как на часах», без часового пояса: встречи очные,
    все в одном городе. SQLite пояс всё равно не хранит, а фронт, получив время
    без пояса, читает его как местное — поэтому UTC с «Z» сдвигал время назад
    на каждом сохранении. Пришло с поясом — оставляем цифры, пояс отбрасываем."""
    if value is not None and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    start_at: datetime
    end_at: datetime | None = None

    _naive = field_validator("start_at", "end_at")(_wall_clock)


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None

    _naive = field_validator("start_at", "end_at")(_wall_clock)


class EventPerson(BaseModel):
    id: int
    full_name: str


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    location: str | None
    start_at: datetime
    end_at: datetime | None
    created_by_id: int
    created_at: datetime
    # «Приду / Не приду»: свой ответ и сколько ответили. Имена — только админам,
    # остальным списки приходят пустыми.
    my_rsvp: Literal["going", "not_going"] | None = None
    going_count: int = 0
    not_going_count: int = 0
    going: list[EventPerson] = []
    not_going: list[EventPerson] = []


class EventRsvpIn(BaseModel):
    # null — снять свой ответ.
    status: Literal["going", "not_going"] | None