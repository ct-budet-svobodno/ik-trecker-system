from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class DirectionHeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: UserRole


class DirectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_code: str
    color: str
    sort_order: int
    heads: list[DirectionHeadOut] = []


class DirectionHeadsUpdate(BaseModel):
    user_ids: list[int]
