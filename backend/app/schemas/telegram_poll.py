from pydantic import BaseModel, Field, field_validator


class TelegramPollIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    options: list[str] = Field(min_length=2, max_length=8)
    chat_id: int | None = Field(default=None, lt=0)
    user_ids: list[int] = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value):
        if not value.strip():
            raise ValueError("Напишите сообщение")
        return value.strip()

    @field_validator("options")
    @classmethod
    def clean_options(cls, values):
        values = [v.strip() for v in values]
        if any(not v or len(v) > 64 for v in values) or len(set(values)) != len(values):
            raise ValueError("Варианты должны отличаться и содержать от 1 до 64 символов")
        return values


class TelegramPollChatIn(BaseModel):
    chat_id: int = Field(lt=0, strict=True)


class TelegramPollVoteIn(BaseModel):
    chat_id: int | None = None
    poll_id: int = Field(gt=0)
    telegram_id: int = Field(gt=0)
    choice: int = Field(ge=0, le=7, strict=True)
