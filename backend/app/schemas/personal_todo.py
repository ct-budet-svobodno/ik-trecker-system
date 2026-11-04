import datetime

from pydantic import BaseModel, ConfigDict, Field


class PersonalTodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: datetime.date


class PersonalTodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None
    # Перенос пункта на другой день.
    date: datetime.date | None = None


class PersonalTodoCarryOver(BaseModel):
    # День, на который переносим всё невыполненное из прошлых дней.
    date: datetime.date


class PersonalTodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime.date
    title: str
    done: bool
    created_at: datetime.datetime
