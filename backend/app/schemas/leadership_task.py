import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.user import LeadershipPosition
from app.models.leadership_task import LeadershipTaskStatus
from app.schemas.direction import DirectionOut


class LeadershipTaskAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


# Порядок строк четвёрки в сетке — задаёт, какие должности «соседние»
# для вертикального объединения блока (position … position_end).
POSITION_ORDER: list[LeadershipPosition] = [
    LeadershipPosition.CHAIRMAN,
    LeadershipPosition.SECRETARY,
    LeadershipPosition.FIRST_DEPUTY,
    LeadershipPosition.BRAND_MANAGER,
]

# Разрешённые цвета блоков четвёрки (hex). None — цвет по умолчанию.
ALLOWED_COLORS: set[str] = {
    "#e0533d",  # красный
    "#e08a3d",  # оранжевый
    "#d9b13d",  # жёлтый
    "#4caf6d",  # зелёный
    "#3d9fa8",  # бирюзовый
    "#3d7de0",  # синий
    "#7c5cff",  # фиолетовый
    "#c85cc8",  # розовый
    "#7a8391",  # серый
}


class LeadershipTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # Ровно одно из трёх: направление, должность тройки или Редакция.
    direction_id: int | None = None
    position: LeadershipPosition | None = None
    is_editorial: bool = False
    date: datetime.date
    status: LeadershipTaskStatus = LeadershipTaskStatus.TODO
    # Объединение в блок (только для четвёрки): конец по дням и по должностям.
    end_date: datetime.date | None = None
    position_end: LeadershipPosition | None = None
    color: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        targets = [self.direction_id is not None, self.position is not None, self.is_editorial]
        if sum(targets) != 1:
            raise ValueError("Укажите ровно одно: direction_id, position или is_editorial")
        _validate_span(self.position, self.position_end, self.date, self.end_date)
        _validate_color(self.color)
        return self


class LeadershipTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    date: datetime.date | None = None
    status: LeadershipTaskStatus | None = None
    color: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        _validate_color(self.color)
        return self


def _validate_span(
    position: LeadershipPosition | None,
    position_end: LeadershipPosition | None,
    date: datetime.date,
    end_date: datetime.date | None,
) -> None:
    if end_date is not None and end_date < date:
        raise ValueError("Дата конца блока не может быть раньше даты начала")
    if position_end is not None:
        if position is None:
            raise ValueError("position_end допустим только вместе с position")
        if POSITION_ORDER.index(position_end) < POSITION_ORDER.index(position):
            raise ValueError("position_end должен идти не выше position по порядку строк")


def _validate_color(color: str | None) -> None:
    if color is not None and color not in ALLOWED_COLORS:
        raise ValueError("Недопустимый цвет")


class LeadershipTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: datetime.date
    end_date: datetime.date | None
    status: LeadershipTaskStatus
    direction_id: int | None
    direction: DirectionOut | None
    position: LeadershipPosition | None
    position_end: LeadershipPosition | None
    is_editorial: bool
    color: str | None
    created_by_id: int
    created_by: LeadershipTaskAuthor
    created_at: datetime.datetime
