from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.task import TaskPriority, TaskStatus
from app.models.user import UserRole
from app.schemas.direction import DirectionOut


class AssigneeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: UserRole


class TaskAssigneeOut(BaseModel):
    """Исполнитель поручения и его личный статус."""

    model_config = ConfigDict(from_attributes=True)

    user: AssigneeSummary
    status: TaskStatus


MAX_ASSIGNEES = 20


def _unique(ids: list[int]) -> list[int]:
    return list(dict.fromkeys(ids))


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    # Обычной задаче направление обязательно, личному поручению — не нужно.
    direction_id: int | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    # Поручение можно дать сразу нескольким; у обычной задачи исполнитель один.
    assignee_ids: list[int] | None = Field(default=None, max_length=MAX_ASSIGNEES)
    due_date: date | None = None
    is_private: bool = False

    @model_validator(mode="after")
    def _validate(self):
        if self.is_private:
            ids = _unique(self.assignee_ids or ([self.assignee_id] if self.assignee_id else []))
            if not ids:
                raise ValueError("Личному поручению нужен исполнитель")
            self.assignee_ids, self.assignee_id = ids, ids[0]
            # Поручение живёт вне направлений.
            self.direction_id = None
        else:
            if self.assignee_ids:
                raise ValueError("Несколько исполнителей бывает только у поручения")
            if self.direction_id is None:
                raise ValueError("Укажите направление")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    direction_id: int | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    assignee_id: int | None = None
    assignee_ids: list[int] | None = Field(default=None, min_length=1, max_length=MAX_ASSIGNEES)
    due_date: date | None = None

    @model_validator(mode="after")
    def _dedupe(self):
        if self.assignee_ids is not None:
            self.assignee_ids = _unique(self.assignee_ids)
        return self


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    # У поручения — статус смотрящего, если он исполнитель; иначе сводный.
    status: TaskStatus
    # Сводный статус поручения по всем исполнителям (у обычной задачи = status).
    overall_status: TaskStatus | None = None
    priority: TaskPriority
    due_date: date | None
    direction: DirectionOut | None
    is_private: bool
    assignee: AssigneeSummary | None
    # Исполнители поручения со своими статусами (у обычной задачи — пусто).
    assignees: list[TaskAssigneeOut] = []
    created_by_id: int
    created_by: AssigneeSummary
    created_at: datetime
    # Последнее напоминание автора о поручении.
    reminded_at: datetime | None = None
    comments_count: int = 0
    # Права смотрящего — чтобы фронт не повторял правила бэка:
    # can_manage — править и удалять, can_comment — писать в обсуждение.
    can_manage: bool = False
    can_comment: bool = False

    @field_validator("reminded_at")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        # В базе — UTC без пояса; отдаём с поясом, иначе браузер прочтёт как местное.
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    parent_id: int | None = None


class TaskCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    author_id: int
    author: AssigneeSummary
    body: str
    parent_id: int | None
    created_at: datetime
    # Для общего компонента обсуждения (CommentThread): у ТЗ «решено» нет.
    resolved: bool = False

    @field_validator("created_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
