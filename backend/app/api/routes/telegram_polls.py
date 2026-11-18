import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import settings
from app.db.session import get_db
from app.models.telegram_poll import TelegramPoll, TelegramPollChat
from app.models.user import User, UserRole
from app.repositories import telegram_poll_repository as repo
from app.schemas.telegram_poll import TelegramPollIn, TelegramPollVoteIn, TelegramPollChatIn
from app.services import telegram_poll_service as service

router = APIRouter()
admin_only = require_role(UserRole.ADMIN)


@router.get("")
def overview(db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return {"chats": [{"id": c.id, "title": c.title} for c in db.scalars(select(TelegramPollChat).order_by(TelegramPollChat.title))], "audience": [dict(id=u.id, full_name=u.full_name, telegram_linked=u.telegram_id is not None,
                             is_activist=u.is_activist) for u in repo.audience(db)],
            "enabled": bool(settings.telegram_bot_token),
            "items": [service.view(db, p) for p in repo.list_all(db)]}


@router.post("", status_code=201)
def create(data: TelegramPollIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    try:
        return service.view(db, service.create(db, admin, data), detail=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/chats")
def add_chat(data: TelegramPollChatIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    try:
        return service.add_chat(db, data.chat_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/vote")
async def vote(request: Request, db: Session = Depends(get_db)):
    # Доверяем только своему polling-боту: HMAC связывает время и всё тело запроса.
    raw = await request.body()
    stamp = request.headers.get("X-Poll-Time", "")
    signature = request.headers.get("X-Poll-Signature", "")
    try:
        fresh = abs(time.time() - int(stamp)) < 60
    except ValueError:
        fresh = False
    expected = hmac.new(settings.telegram_bot_token.encode(),
                        stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not settings.telegram_bot_token or not fresh or not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Неверная подпись бота")
    try:
        data = TelegramPollVoteIn.model_validate_json(raw)
    except ValueError:
        raise HTTPException(422, "Некорректный голос")
    try:
        return {"choice": service.vote(db, data)}
    except ValueError as exc:
        raise HTTPException(409, str(exc))


def _get(db, poll_id):
    poll = db.get(TelegramPoll, poll_id)
    if poll is None:
        raise HTTPException(404, "Опрос не найден")
    return poll


@router.get("/{poll_id}")
def detail(poll_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return service.view(db, _get(db, poll_id), detail=True)


@router.put("/{poll_id}/closed")
def close(poll_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    poll = _get(db, poll_id)
    poll.closed = True
    db.commit()
    return service.view(db, poll, detail=True)
