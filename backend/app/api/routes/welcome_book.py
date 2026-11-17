from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.services import welcome_book_service as service

router = APIRouter()


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
