from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.activities.checklist_facts import DEFAULT_FACTS
from app.api.deps import require_role
from app.db.session import get_db
from app.models.checklist import ChecklistCard
from app.models.user import User, UserRole
from app.schemas.checklist import (
    ChecklistByTag,
    ChecklistCardOut,
    ChecklistOverview,
    ChecklistPrepare,
    ChecklistTagCard,
)
from app.services import bot_sync_service, checklist_service, telegram_service
from app.services.exceptions import ChecklistError

# Чек-листы «Найди того, кто…» — только админ.
router = APIRouter()
admin_only = require_role(UserRole.ADMIN)


def _out(card: ChecklistCard, photos: dict[int, list]) -> dict:
    got = photos.get(card.tg_id, [None] * 3)
    return {
        "id": card.id,
        "number": card.number,
        "tg_id": card.tg_id,
        "full_name": card.full_name,
        "username": card.username,
        "facts": card.facts,
        "image_ready": card.image_ready,
        "status": card.status,
        "sent_at": card.sent_at,
        "photos": [bool(p) for p in got],
    }


def _overview(db: Session) -> dict:
    photos = checklist_service.bot_photos()
    return {
        "default_facts": DEFAULT_FACTS,
        "cards": [_out(c, photos) for c in checklist_service.list_cards(db)],
        "people": checklist_service.people_count(db),
        "sending": checklist_service.is_sending(),
        "enabled": telegram_service.telegram_enabled() and bot_sync_service.enabled(),
    }


@router.get("", response_model=ChecklistOverview)
def overview(db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    return _overview(db)


@router.post("/prepare", response_model=ChecklistOverview)
def prepare(payload: ChecklistPrepare, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        checklist_service.prepare(db, payload.facts)
    except ChecklistError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _overview(db)


@router.put("/cards/{card_id}/image", status_code=status.HTTP_204_NO_CONTENT)
async def upload_image(
    card_id: int, image: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(admin_only)
) -> None:
    data = await image.read(checklist_service.MAX_IMAGE_BYTES + 1)
    try:
        checklist_service.save_image(db, card_id, data)
    except ChecklistError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/cards/{card_id}/image")
def get_image(card_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> Response:
    data = checklist_service.image(db, card_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Картинки нет")
    return Response(content=data, media_type="image/jpeg")


@router.get("/cards/{card_id}/photo/{slot}")
def get_photo(
    card_id: int, slot: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)
) -> Response:
    data = checklist_service.photo(db, card_id, slot)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фото нет")
    return Response(content=data, media_type="image/jpeg")


@router.post("/send", response_model=ChecklistOverview)
def send(db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        checklist_service.start_sending(db)
    except ChecklistError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _overview(db)


@router.post("/send-test", response_model=ChecklistOverview)
def send_test(db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        checklist_service.send_test(db, admin)
    except ChecklistError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _overview(db)


@router.post("/by-tag", response_model=ChecklistTagCard)
def card_by_tag(payload: ChecklistByTag, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    """Не дошло или человека не было в раздаче: найти по тегу и отдать его лист
    (новый — со свободными фактами); отправка — /cards/{id}/send."""
    try:
        card, needs_image = checklist_service.card_for_tag(db, payload.username)
    except ChecklistError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"card": _out(card, checklist_service.bot_photos()), "needs_image": needs_image}


@router.post("/cards/{card_id}/send", response_model=ChecklistOverview)
def send_card(card_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        checklist_service.send_one(db, card_id)
    except ChecklistError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _overview(db)


@router.post("/reset", response_model=ChecklistOverview)
def reset(db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        checklist_service.reset(db)
    except ChecklistError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _overview(db)
