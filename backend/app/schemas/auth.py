from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TelegramInitData(BaseModel):
    # Строка Telegram.WebApp.initData как есть.
    init_data: str = Field(min_length=1, max_length=8192)


class TelegramConfig(BaseModel):
    enabled: bool
    bot_username: str | None = None


class TelegramClaim(BaseModel):
    """Привязка Telegram к существующему аккаунту по коду из веб-версии."""

    init_data: str = Field(min_length=1, max_length=8192)
    code: str = Field(min_length=4, max_length=32)


class TelegramLinkCode(BaseModel):
    code: str
    # Ссылка, открывающая мини-апп с этим кодом (startapp=link_<код>).
    url: str | None


class RegistrationDirection(BaseModel):
    id: int
    name: str


class RegistrationOptions(BaseModel):
    """Что нужно форме анкеты до входа: направления и размеры."""

    directions: list[RegistrationDirection]
    clothes_sizes: list[str]
