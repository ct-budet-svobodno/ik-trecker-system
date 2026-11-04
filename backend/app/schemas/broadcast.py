import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.broadcast import BroadcastStatus


class BroadcastButton(BaseModel):
    text: str = Field(min_length=1, max_length=64)
    # Ровно одно из двух: ссылка наружу или страница трекера (мини-апп).
    url: str | None = Field(default=None, max_length=512)
    path: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _target(self):
        if bool(self.url) == bool(self.path):
            raise ValueError("У кнопки должна быть либо ссылка, либо раздел трекера")
        if self.url and not self.url.startswith(("https://", "http://")):
            raise ValueError("Ссылка должна начинаться с https://")
        if self.path and not self.path.startswith("/"):
            raise ValueError("Раздел трекера — путь от корня, например /games")
        return self


class BroadcastIn(BaseModel):
    # Telegram принимает до 4096 символов; с разметкой — запас.
    text: str = Field(min_length=1, max_length=3500)
    buttons: list[BroadcastButton] = Field(default_factory=list, max_length=8)


class BroadcastOut(BaseModel):
    id: int
    text: str
    buttons: list[dict]
    status: BroadcastStatus
    total: int
    sent: int
    failed: int
    author_name: str | None
    created_at: datetime.datetime
    finished_at: datetime.datetime | None


class BroadcastOverview(BaseModel):
    recipients: int  # сколько человек получат рассылку сейчас
    enabled: bool  # бот подключён
    has_telegram: bool  # у админа привязан Telegram — можно проверить на себе
    items: list[BroadcastOut]
