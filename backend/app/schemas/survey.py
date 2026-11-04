import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.survey import SurveyStatus

QuestionType = Literal["text", "textarea", "single", "multi", "scale"]


class SurveyQuestion(BaseModel):
    # id задаёт фронт (короткая строка) — по нему хранятся ответы,
    # поэтому вопросы можно переставлять, не теряя их.
    id: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    type: QuestionType
    title: str = Field(min_length=1, max_length=300)
    hint: str = Field(default="", max_length=300)
    required: bool = True
    # Варианты — для single/multi.
    options: list[str] = Field(default_factory=list, max_length=30)
    # Шкала 1…max — для scale.
    max: int = Field(default=5, ge=2, le=10)

    @model_validator(mode="after")
    def _shape(self):
        self.title = self.title.strip()
        self.options = [o.strip() for o in self.options]
        if self.type in ("single", "multi"):
            if len(self.options) < 2:
                raise ValueError(f"В вопросе «{self.title}» нужно хотя бы два варианта")
            if any(not o or len(o) > 200 for o in self.options):
                raise ValueError(f"В вопросе «{self.title}» пустой или слишком длинный вариант")
            if len(set(self.options)) != len(self.options):
                raise ValueError(f"В вопросе «{self.title}» варианты повторяются")
        else:
            self.options = []
        return self


class SurveyIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    questions: list[SurveyQuestion] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("У вопросов повторяются id")
        return self


class SurveySendIn(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=1000)


class SurveyStatusIn(BaseModel):
    status: Literal["open", "closed"]


class SurveyResponseIn(BaseModel):
    answers: dict[str, str | int | list[str] | None]


class SurveySummaryOut(BaseModel):
    """Строка в списке анкет у админа."""

    id: int
    title: str
    status: SurveyStatus
    questions_count: int
    recipients: int
    responses: int
    author_name: str | None
    created_at: datetime.datetime


class SurveyRecipientOut(BaseModel):
    user_id: int
    full_name: str
    telegram_username: str | None
    telegram_linked: bool
    sent_at: datetime.datetime | None
    answers: dict | None  # None — ещё не ответил
    submitted_at: datetime.datetime | None


class SurveyAdminOut(BaseModel):
    id: int
    title: str
    description: str
    questions: list[dict]
    status: SurveyStatus
    author_name: str | None
    created_at: datetime.datetime
    reminded_at: datetime.datetime | None
    # Вопросы правятся, пока никто не ответил.
    can_edit_questions: bool
    recipients: list[SurveyRecipientOut]


class SurveySendOut(BaseModel):
    added: int  # новые получатели
    already: int  # уже получали
    without_telegram: int  # из новых — без Telegram: увидят анкету только в трекере


class SurveyRemindOut(BaseModel):
    reminded: int


class MySurveyOut(BaseModel):
    """Анкета у получателя: в списке и на странице ответа."""

    id: int
    title: str
    description: str
    questions: list[dict]
    status: SurveyStatus
    answers: dict | None
    submitted_at: datetime.datetime | None
    sent_at: datetime.datetime | None
