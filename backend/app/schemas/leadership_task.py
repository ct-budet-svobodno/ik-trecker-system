import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.user import LeadershipPosition
from app.models.leadership_task import LeadershipTaskStatus
from app.schemas.direction import DirectionOut


class LeadershipTaskAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class LeadershipTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # Ровно одно из двух: направление или должность тройки.
    direction_id: int | None = None
    position: LeadershipPosition | None = None
    date: datetime.date
    status: LeadershipTaskStatus = LeadershipTaskStatus.TODO

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if (self.direction_id is None) == (self.position is None):
            raise ValueError("Укажите ровно одно: direction_id или position")
        return self


class LeadershipTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    date: datetime.date | None = None
    status: LeadershipTaskStatus | None = None


class LeadershipTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: datetime.date
    status: LeadershipTaskStatus
    direction_id: int | None
    direction: DirectionOut | None
    position: LeadershipPosition | None
    created_by_id: int
    created_by: LeadershipTaskAuthor
    created_at: datetime.datetime
