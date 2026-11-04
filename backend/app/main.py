from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.services import bot_import_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Анкеты из бота → аккаунты трекера: сразу и дальше по расписанию.
    bot_import_service.start_background()
    yield


app = FastAPI(title="ИК Таск-трекер API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
