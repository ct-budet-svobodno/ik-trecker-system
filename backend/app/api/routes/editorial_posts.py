from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.editorial_post import EditorialPost
from app.models.user import User
from app.repositories import editorial_post_repository
from app.schemas.editorial_post import (
    EditorialAssignRequest,
    EditorialCommentCreate,
    EditorialCommentUpdate,
    EditorialPostCreate,
    EditorialPostDetailOut,
    EditorialPostOut,
    EditorialPostUpdate,
)
from app.services import editorial_service
from app.services.exceptions import (
    EditorialAccessError,
    EditorialPostNotFoundError,
    UserNotFoundError,
)

# Гейт членства — в сервисе (не-участник получает 403), роут требует лишь авторизацию.
router = APIRouter(dependencies=[Depends(get_current_user)])


def _access(exc: EditorialAccessError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


def _not_found(detail: str = "Пост не найден") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _get_post_or_404(db: Session, post_id: int) -> EditorialPost:
    post = editorial_post_repository.get_by_id(db, post_id)
    if post is None:
        raise _not_found()
    return post


@router.get("", response_model=list[EditorialPostOut])
def list_posts(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EditorialPost]:
    try:
        return editorial_service.list_in_range(db, current_user, date_from, date_to)
    except EditorialAccessError as exc:
        raise _access(exc)


@router.get("/mine", response_model=list[EditorialPostOut])
def list_my_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EditorialPost]:
    """Посты, где я райтер/дизайнер — для блока «Мои посты» на доске задач."""
    return editorial_service.list_mine(db, current_user)


@router.get("/{post_id}", response_model=EditorialPostDetailOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    try:
        return editorial_service.get_detail(db, current_user, post_id)
    except EditorialAccessError as exc:
        raise _access(exc)
    except EditorialPostNotFoundError:
        raise _not_found()


@router.post("", response_model=EditorialPostDetailOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: EditorialPostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    try:
        post = editorial_service.create(db, current_user, payload)
    except EditorialAccessError as exc:
        raise _access(exc)
    return editorial_post_repository.get_by_id(db, post.id)


@router.patch("/{post_id}", response_model=EditorialPostDetailOut)
def update_post(
    post_id: int,
    payload: EditorialPostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    post = _get_post_or_404(db, post_id)
    try:
        return editorial_service.update(db, current_user, post, payload)
    except EditorialAccessError as exc:
        raise _access(exc)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    post = _get_post_or_404(db, post_id)
    try:
        editorial_service.delete(db, current_user, post)
    except EditorialAccessError as exc:
        raise _access(exc)


@router.post("/{post_id}/assign", response_model=EditorialPostDetailOut)
def assign_role(
    post_id: int,
    payload: EditorialAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    post = _get_post_or_404(db, post_id)
    try:
        return editorial_service.assign_role(
            db, current_user, post, payload.role, payload.user_id
        )
    except EditorialAccessError as exc:
        raise _access(exc)
    except UserNotFoundError as exc:
        raise _not_found(str(exc))


@router.delete("/{post_id}/assign/{role}", response_model=EditorialPostDetailOut)
def unassign_role(
    post_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    if role not in ("writer", "designer", "editor"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Неизвестная роль")
    post = _get_post_or_404(db, post_id)
    try:
        return editorial_service.unassign_role(db, current_user, post, role)
    except EditorialAccessError as exc:
        raise _access(exc)


@router.post("/{post_id}/comments", response_model=EditorialPostDetailOut)
def add_comment(
    post_id: int,
    payload: EditorialCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    post = _get_post_or_404(db, post_id)
    try:
        return editorial_service.add_comment(
            db,
            current_user,
            post,
            target=payload.target,
            body=payload.body,
            parent_id=payload.parent_id,
        )
    except EditorialAccessError as exc:
        raise _access(exc)
    except EditorialPostNotFoundError as exc:
        raise _not_found(str(exc))


@router.patch("/{post_id}/comments/{comment_id}", response_model=EditorialPostDetailOut)
def update_comment(
    post_id: int,
    comment_id: int,
    payload: EditorialCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    post = _get_post_or_404(db, post_id)
    comment = editorial_post_repository.get_comment(db, comment_id)
    if comment is None or comment.post_id != post.id:
        raise _not_found("Комментарий не найден")
    try:
        return editorial_service.set_comment_resolved(
            db, current_user, post, comment, payload.resolved
        )
    except EditorialAccessError as exc:
        raise _access(exc)


@router.delete("/{post_id}/comments/{comment_id}", response_model=EditorialPostDetailOut)
def delete_comment(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditorialPost:
    post = _get_post_or_404(db, post_id)
    comment = editorial_post_repository.get_comment(db, comment_id)
    if comment is None or comment.post_id != post.id:
        raise _not_found("Комментарий не найден")
    try:
        return editorial_service.delete_comment(db, current_user, post, comment)
    except EditorialAccessError as exc:
        raise _access(exc)
