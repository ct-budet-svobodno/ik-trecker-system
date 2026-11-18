from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.welcome_book import WelcomeBookProgressIn
from app.services import welcome_book_service as service

router = APIRouter()


@router.put("/progress", status_code=204)
def save_progress(payload: WelcomeBookProgressIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        service.record_progress(db, current_user.id, payload.version, payload.page)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/readers")
def get_readers(db: Session = Depends(get_db), current_user: User = Depends(require_role(UserRole.ADMIN))):
    return service.readers(db)


@router.get("")
def get_book(current_user: User = Depends(get_current_user)):
    return service.metadata()


@router.get("/pdf")
def get_pdf(current_user: User = Depends(get_current_user)):
    try:
        data = service.book_path().read_bytes()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Велкомбук пока не загружен")
    return Response(data, media_type="application/pdf", headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": 'inline; filename="welcome-book.pdf"',
    })


@router.put("")
async def upload_book(request: Request, current_user: User = Depends(require_role(UserRole.ADMIN))):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > service.MAX_BYTES:
            raise HTTPException(status_code=413, detail="PDF должен быть не больше 18 МБ")
        data.extend(chunk)
    try:
        return await run_in_threadpool(service.publish, bytes(data))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
