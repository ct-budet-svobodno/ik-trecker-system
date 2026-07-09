from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadershipNoteAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class LeadershipNoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=8000)


class LeadershipNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    created_by_id: int
    created_by: LeadershipNoteAuthor
    created_at: datetime
