from datetime import date

from sqlalchemy.orm import Session

from app.models.editorial_post import (
    EditorialComment,
    EditorialCommentTarget,
    EditorialPost,
    EditorialStatus,
)
from app.models.user import User, UserRole
from app.repositories import (
    direction_repository,
    editorial_post_repository,
    user_repository,
)
from app.schemas.editorial_post import EditorialPostCreate, EditorialPostUpdate
from app.services import push_service
from app.services.exceptions import (
    EditorialAccessError,
    EditorialPostNotFoundError,
    UserNotFoundError,
)

# Направления Редакции опознаём по короткому коду (как и цвета направлений).
SMI_SHORT_CODE = "СМИ"
DESIGN_SHORT_CODE = "Дизайн"


# --- Права ---

def _heads_direction(db: Session, user: User, short_code: str) -> bool:
    dir_id = direction_repository.get_id_by_short_code(db, short_code)
    return dir_id is not None and dir_id in direction_repository.list_ids_headed_by(db, user.id)


def is_text_reviewer(db: Session, user: User) -> bool:
    """Кто принимает/правит текст: руководитель СМИ или админ."""
    return user.role == UserRole.ADMIN or _heads_direction(db, user, SMI_SHORT_CODE)


def is_design_reviewer(db: Session, user: User) -> bool:
    """Кто принимает/правит дизайн: руководитель Дизайна или админ."""
    return user.role == UserRole.ADMIN or _heads_direction(db, user, DESIGN_SHORT_CODE)


def is_editor(db: Session, user: User) -> bool:
    """Редактор: создаёт посты, правит описание, назначает роли.
    Это админ или руководитель СМИ/Дизайна."""
    return is_text_reviewer(db, user) or is_design_reviewer(db, user)


def is_member(db: Session, user: User) -> bool:
    """Участник Редакции: личный флаг или редактор."""
    return bool(user.is_editorial) or is_editor(db, user)


def can_view(db: Session, user: User) -> bool:
    """Кто видит календарь Редакции: руководители (admin/manager), «четвёрка»
    (должность руководства) и активисты СМИ/Дизайна (флаг is_editorial)."""
    return (
        user.role in (UserRole.ADMIN, UserRole.MANAGER)
        or user.leadership_position is not None
        or is_member(db, user)
    )


def _is_writer(user: User, post: EditorialPost) -> bool:
    return post.writer_id == user.id


def _is_designer(user: User, post: EditorialPost) -> bool:
    return post.designer_id == user.id


def _is_post_editor(user: User, post: EditorialPost) -> bool:
    """Назначенный редактор конкретного поста (третья роль рядом с райтером и дизайнером)."""
    return post.editor_id == user.id


def _is_editor_for(db: Session, user: User, post: EditorialPost) -> bool:
    """Права редактора в рамках поста: глобальный редактор или редактор этого поста."""
    return _is_post_editor(user, post) or is_editor(db, user)


def _ensure_member(db: Session, viewer: User) -> None:
    if not is_member(db, viewer):
        raise EditorialAccessError("Доступ только для участников Редакции")


def _ensure_editor(db: Session, viewer: User) -> None:
    if not is_editor(db, viewer):
        raise EditorialAccessError("Действие доступно только редактору")


# --- Пуш-уведомления ---

def _reviewer_ids(db: Session, short_code: str) -> list[int]:
    """id ревьюеров трека: руководители СМИ (текст) или Дизайна (дизайн)."""
    dir_id = direction_repository.get_id_by_short_code(db, short_code)
    direction = direction_repository.get_by_id(db, dir_id) if dir_id else None
    return [h.id for h in (direction.heads if direction else [])]


def _track_author_id(post: EditorialPost, target: EditorialCommentTarget) -> int | None:
    return post.writer_id if target == EditorialCommentTarget.TEXT else post.designer_id


def _push(db: Session, user_ids: list[int], actor: User, title: str, post: EditorialPost) -> None:
    targets = [uid for uid in user_ids if uid and uid != actor.id]
    push_service.send_to_users(
        db, targets, title=title, body=post.title, url=f"/editorial/{post.id}"
    )


# --- Чтение ---

def list_in_range(db: Session, viewer: User, date_from: date, date_to: date) -> list[EditorialPost]:
    if not can_view(db, viewer):
        raise EditorialAccessError("Доступ только для Редакции и руководителей")
    return editorial_post_repository.list_in_range(db, date_from, date_to)


def get_detail(db: Session, viewer: User, post_id: int) -> EditorialPost:
    post = editorial_post_repository.get_by_id(db, post_id)
    if post is None:
        raise EditorialPostNotFoundError("Пост не найден")
    # Назначенный райтер/дизайнер/редактор видит свой пост, даже если он не из Редакции.
    is_assigned = viewer.id in (post.writer_id, post.designer_id, post.editor_id)
    if not (is_assigned or can_view(db, viewer)):
        raise EditorialAccessError("Доступ только для Редакции и руководителей")
    return post


def list_mine(db: Session, viewer: User) -> list[EditorialPost]:
    """Посты, где пользователь — райтер, дизайнер или редактор. Доступно всем авторизованным."""
    return editorial_post_repository.list_assigned_to(db, viewer.id)


# --- Создание / изменение ---

def create(db: Session, viewer: User, payload: EditorialPostCreate) -> EditorialPost:
    _ensure_editor(db, viewer)
    return editorial_post_repository.create(
        db,
        date=payload.date,
        title=payload.title,
        format=payload.format,
        brief=payload.brief,
        reference=payload.reference,
        created_by_id=viewer.id,
    )


def update(
    db: Session, viewer: User, post: EditorialPost, payload: EditorialPostUpdate
) -> EditorialPost:
    _ensure_member(db, viewer)
    provided = payload.model_fields_set
    changes: dict = {}

    # Описание поста — только редактор (глобальный или редактор этого поста).
    meta = ["title", "date", "format", "brief", "reference"]
    if any(field in provided for field in meta):
        if not _is_editor_for(db, viewer, post):
            raise EditorialAccessError("Действие доступно только редактору")
        for field in meta:
            if field in provided:
                changes[field] = getattr(payload, field)

    # Текст — назначенный райтер или редактор.
    if "text_content" in provided:
        if not (_is_writer(viewer, post) or _is_editor_for(db, viewer, post)):
            raise EditorialAccessError("Текст может править только райтер")
        changes["text_content"] = payload.text_content

    if "text_status" in provided:
        _ensure_text_status_change(db, viewer, post, payload.text_status)
        changes["text_status"] = payload.text_status

    # Дизайн — назначенный дизайнер или редактор.
    if "figma_url" in provided or "design_done" in provided:
        if not (_is_designer(viewer, post) or _is_editor_for(db, viewer, post)):
            raise EditorialAccessError("Дизайн может править только дизайнер")
        if "figma_url" in provided:
            changes["figma_url"] = payload.figma_url
        if "design_done" in provided:
            changes["design_done"] = payload.design_done

    if "design_status" in provided:
        _ensure_design_status_change(db, viewer, post, payload.design_status)
        changes["design_status"] = payload.design_status

    if changes:
        editorial_post_repository.update_fields(db, post, changes)
        _notify_status_changes(db, viewer, post, changes)
    return editorial_post_repository.get_by_id(db, post.id)


_STATUS_PUSH = {
    EditorialStatus.REVIEW: ("{} на проверке", "reviewers"),
    EditorialStatus.FIXES: ("{}: вернули на правки", "author"),
    EditorialStatus.READY: ("{}: принято", "author"),
}


def _notify_status_changes(db: Session, viewer: User, post: EditorialPost, changes: dict) -> None:
    tracks = [
        ("text_status", "Текст", SMI_SHORT_CODE, post.writer_id),
        ("design_status", "Дизайн", DESIGN_SHORT_CODE, post.designer_id),
    ]
    for field, label, reviewer_code, author_id in tracks:
        new_status = changes.get(field)
        if new_status not in _STATUS_PUSH:
            continue
        title_tpl, audience = _STATUS_PUSH[new_status]
        targets = _reviewer_ids(db, reviewer_code) if audience == "reviewers" else [author_id]
        _push(db, targets, viewer, title_tpl.format(label), post)


def _ensure_text_status_change(
    db: Session, viewer: User, post: EditorialPost, new: EditorialStatus
) -> None:
    # Автор/редактор могут отправить на проверку или вернуть в черновик;
    # вернуть на правки / принять / снять — ревьюер текста или редактор поста.
    if new in (EditorialStatus.REVIEW, EditorialStatus.DRAFT):
        if _is_writer(viewer, post) or _is_editor_for(db, viewer, post) or is_text_reviewer(db, viewer):
            return
    elif is_text_reviewer(db, viewer) or _is_post_editor(viewer, post):
        return
    raise EditorialAccessError("Недостаточно прав для смены статуса текста")


def _ensure_design_status_change(
    db: Session, viewer: User, post: EditorialPost, new: EditorialStatus
) -> None:
    if new in (EditorialStatus.REVIEW, EditorialStatus.DRAFT):
        if _is_designer(viewer, post) or _is_editor_for(db, viewer, post) or is_design_reviewer(db, viewer):
            return
    elif is_design_reviewer(db, viewer) or _is_post_editor(viewer, post):
        return
    raise EditorialAccessError("Недостаточно прав для смены статуса дизайна")


def delete(db: Session, viewer: User, post: EditorialPost) -> None:
    _ensure_editor(db, viewer)
    editorial_post_repository.delete(db, post)


# --- Роли ---

_ROLE_LABELS = {"writer": "райтером", "designer": "дизайнером", "editor": "редактором"}


def assign_role(
    db: Session, viewer: User, post: EditorialPost, role: str, user_id: int | None
) -> EditorialPost:
    _ensure_member(db, viewer)

    # Слот редактора раздаёт только глобальный редактор (роль даёт права на пост).
    if role == "editor" and not is_editor(db, viewer):
        raise EditorialAccessError("Назначить редактора поста может только редактор")

    target_id = viewer.id if user_id is None else user_id
    assigning_other = target_id != viewer.id
    if assigning_other and not _is_editor_for(db, viewer, post):
        raise EditorialAccessError("Назначать других может только редактор")

    if user_id is not None and user_repository.get_by_id(db, user_id) is None:
        raise UserNotFoundError("Пользователь не найден")

    slot_field = f"{role}_id"
    current = getattr(post, slot_field)
    # Самозапись — только в пустой слот; редактор может переназначать.
    if current is not None and current != target_id and not _is_editor_for(db, viewer, post):
        raise EditorialAccessError("Роль уже занята")

    changes = {slot_field: target_id}
    # Назначение автора переводит трек из «пусто» в «черновик».
    if role == "writer" and post.text_status == EditorialStatus.EMPTY:
        changes["text_status"] = EditorialStatus.DRAFT
    if role == "designer" and post.design_status == EditorialStatus.EMPTY:
        changes["design_status"] = EditorialStatus.DRAFT

    editorial_post_repository.update_fields(db, post, changes)
    _push(db, [target_id], viewer, f"Вас назначили {_ROLE_LABELS[role]}", post)
    return editorial_post_repository.get_by_id(db, post.id)


def unassign_role(db: Session, viewer: User, post: EditorialPost, role: str) -> EditorialPost:
    _ensure_member(db, viewer)
    slot_field = f"{role}_id"
    current = getattr(post, slot_field)
    if current is not None and current != viewer.id and not _is_editor_for(db, viewer, post):
        raise EditorialAccessError("Снять роль может сам исполнитель или редактор")
    editorial_post_repository.update_fields(db, post, {slot_field: None})
    return editorial_post_repository.get_by_id(db, post.id)


# --- Комментарии ---

def _can_comment(db: Session, viewer: User, post: EditorialPost, target: EditorialCommentTarget) -> bool:
    if target == EditorialCommentTarget.TEXT:
        return _is_writer(viewer, post) or is_text_reviewer(db, viewer) or _is_editor_for(db, viewer, post)
    return _is_designer(viewer, post) or is_design_reviewer(db, viewer) or _is_editor_for(db, viewer, post)


def add_comment(
    db: Session,
    viewer: User,
    post: EditorialPost,
    *,
    target: EditorialCommentTarget,
    body: str,
    parent_id: int | None,
) -> EditorialPost:
    _ensure_member(db, viewer)
    if not _can_comment(db, viewer, post, target):
        raise EditorialAccessError("Недостаточно прав, чтобы комментировать")
    if parent_id is not None:
        parent = editorial_post_repository.get_comment(db, parent_id)
        if parent is None or parent.post_id != post.id:
            raise EditorialPostNotFoundError("Комментарий-родитель не найден")
    editorial_post_repository.add_comment(
        db,
        post_id=post.id,
        target=target,
        author_id=viewer.id,
        body=body,
        parent_id=parent_id,
    )
    # Пуш «другой стороне»: автор трека комментирует — ревьюерам, иначе — автору.
    author_id = _track_author_id(post, target)
    if viewer.id == author_id:
        code = SMI_SHORT_CODE if target == EditorialCommentTarget.TEXT else DESIGN_SHORT_CODE
        targets = _reviewer_ids(db, code)
    else:
        targets = [author_id]
    _push(db, targets, viewer, "Новая правка", post)
    return editorial_post_repository.get_by_id(db, post.id)


def set_comment_resolved(
    db: Session, viewer: User, post: EditorialPost, comment: EditorialComment, resolved: bool
) -> EditorialPost:
    _ensure_member(db, viewer)
    is_reviewer = (
        is_text_reviewer(db, viewer)
        if comment.target == EditorialCommentTarget.TEXT
        else is_design_reviewer(db, viewer)
    )
    if not (is_reviewer or _is_editor_for(db, viewer, post) or comment.author_id == viewer.id):
        raise EditorialAccessError("Недостаточно прав, чтобы закрыть комментарий")
    editorial_post_repository.update_comment(db, comment, {"resolved": resolved})
    return editorial_post_repository.get_by_id(db, post.id)


def delete_comment(
    db: Session, viewer: User, post: EditorialPost, comment: EditorialComment
) -> EditorialPost:
    _ensure_member(db, viewer)
    if not (comment.author_id == viewer.id or _is_editor_for(db, viewer, post)):
        raise EditorialAccessError("Удалить комментарий может автор или редактор")
    editorial_post_repository.delete_comment(db, comment)
    return editorial_post_repository.get_by_id(db, post.id)
