import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.zavod import ZavodNodeStatus
# Палитра общая с блоками таймлайна — один набор цветов на весь трекер.
from app.schemas.leadership_task import ALLOWED_COLORS

# Границы холста: карточку нельзя «улететь» в бесконечность и потерять.
COORD_LIMIT = 100_000
MIN_SIZE = 120
MAX_SIZE = 1200


def _validate_color(color: str | None) -> None:
    if color is not None and color not in ALLOWED_COLORS:
        raise ValueError("Недопустимый цвет")


class ZavodNodeAssignee(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class ZavodBoardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ZavodBoardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)


class ZavodBoardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime.datetime


class ZavodNodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str | None = None
    status: ZavodNodeStatus = ZavodNodeStatus.TODO
    color: str | None = None
    x: float = Field(default=0, ge=-COORD_LIMIT, le=COORD_LIMIT)
    y: float = Field(default=0, ge=-COORD_LIMIT, le=COORD_LIMIT)
    width: float = Field(default=220, ge=MIN_SIZE, le=MAX_SIZE)
    height: float = Field(default=120, ge=MIN_SIZE, le=MAX_SIZE)
    assignee_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self):
        _validate_color(self.color)
        return self


class ZavodNodeUpdate(BaseModel):
    """Все поля необязательны: приходит только то, что реально изменилось.

    color здесь особенный — явный null означает «снять цвет», а не «не трогать»,
    поэтому роут смотрит на model_fields_set (как в leadership_tasks).
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    status: ZavodNodeStatus | None = None
    color: str | None = None
    x: float | None = Field(default=None, ge=-COORD_LIMIT, le=COORD_LIMIT)
    y: float | None = Field(default=None, ge=-COORD_LIMIT, le=COORD_LIMIT)
    width: float | None = Field(default=None, ge=MIN_SIZE, le=MAX_SIZE)
    height: float | None = Field(default=None, ge=MIN_SIZE, le=MAX_SIZE)
    assignee_ids: list[int] | None = None

    @model_validator(mode="after")
    def _validate(self):
        _validate_color(self.color)
        return self


class ZavodNodeMove(BaseModel):
    """Один элемент пакетного перетаскивания."""

    id: int
    x: float = Field(ge=-COORD_LIMIT, le=COORD_LIMIT)
    y: float = Field(ge=-COORD_LIMIT, le=COORD_LIMIT)


class ZavodNodesMove(BaseModel):
    """Перетаскивание выделенной группы — одним запросом вместо пачки PATCH."""

    moves: list[ZavodNodeMove] = Field(min_length=1, max_length=200)


class ZavodNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    title: str
    content: str | None
    status: ZavodNodeStatus
    color: str | None
    x: float
    y: float
    width: float
    height: float
    assignees: list[ZavodNodeAssignee]


class ZavodEdgeCreate(BaseModel):
    source_id: int
    target_id: int


class ZavodEdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    source_id: int
    target_id: int


class ZavodBoardDetail(BaseModel):
    """Доска целиком — фронт грузит её одним запросом и дальше работает локально."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    nodes: list[ZavodNodeOut]
    edges: list[ZavodEdgeOut]
