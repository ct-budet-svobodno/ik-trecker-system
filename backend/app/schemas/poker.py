from typing import Literal

from pydantic import BaseModel, Field


class PokerMove(BaseModel):
    action: Literal['fold', 'check', 'call', 'raise', 'all_in']
    version: int
    amount: int | None = Field(default=None, ge=1)


class PokerVersion(BaseModel):
    version: int
