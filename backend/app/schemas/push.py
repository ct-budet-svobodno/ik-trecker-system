from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    """Подписка в формате PushSubscription.toJSON() из браузера."""

    endpoint: str = Field(min_length=1, max_length=500)
    keys: PushKeys


class PushSubscriptionDelete(BaseModel):
    endpoint: str = Field(min_length=1, max_length=500)


class PushPublicKeyOut(BaseModel):
    public_key: str
