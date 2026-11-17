from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.services import bot_import_service, poker_service
from app.db.session import SessionLocal


def _expire_poker_turns():
    with SessionLocal() as db:
        poker_service.expire_turns(db)


async def _poker_clock():
    while True:
        try:
            await asyncio.to_thread(_expire_poker_turns)
        except Exception:
            logging.getLogger(__name__).exception("Не удалось обработать таймеры покера")
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Анкеты из бота → аккаунты трекера: сразу и дальше по расписанию.
    bot_import_service.start_background()
    poker_clock = asyncio.create_task(_poker_clock())
    try:
        yield
    finally:
        poker_clock.cancel()
        await asyncio.gather(poker_clock, return_exceptions=True)


app = FastAPI(title="ИК Таск-трекер API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
