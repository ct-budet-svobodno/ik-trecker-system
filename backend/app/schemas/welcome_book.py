from pydantic import BaseModel, Field


class WelcomeBookProgressIn(BaseModel):
    version: str = Field(pattern=r"^[a-f0-9]{64}$")
    page: int = Field(strict=True, ge=1, le=300)
