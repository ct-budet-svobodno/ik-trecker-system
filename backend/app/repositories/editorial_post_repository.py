from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.editorial_post import (
    EditorialComment,
    EditorialCommentTarget,
    EditorialPost,
)


def _base_query():
    return select(EditorialPost).options(
        joinedload(EditorialPost.writer),
        joinedload(EditorialPost.designer),
        joinedload(EditorialPost.created_by),
    )


def list_in_range(db: Session, date_from: date, date_to: date) -> list[EditorialPost]:
    query = (
        _base_query()
        .where(EditorialPost.date >= date_from, EditorialPost.date <= date_to)
        .order_by(EditorialPost.date, EditorialPost.id)
    )
    return list(db.scalars(query).unique())


def list_assigned_to(db: Session, user_id: int) -> list[EditorialPost]:
    query = (
        _base_query()
        .where((EditorialPost.writer_id == user_id) | (EditorialPost.designer_id == user_id))
        .order_by(EditorialPost.date, EditorialPost.id)
    )
    return list(db.scalars(query).unique())


def get_by_id(db: Session, post_id: int) -> EditorialPost | None:
    query = (
        _base_query()
        .options(selectinload(EditorialPost.comments).joinedload(EditorialComment.author))
        .where(EditorialPost.id == post_id)
    )
    return db.scalar(query)


def create(
    db: Session,
    *,
    date: date,
    title: str,
    format: str | None,
    brief: str,
    reference: str | None,
    created_by_id: int,
) -> EditorialPost:
    post = EditorialPost(
        date=date,
        title=title,
        format=format,
        brief=brief,
        reference=reference,
        created_by_id=created_by_id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def update_fields(db: Session, post: EditorialPost, fields: dict) -> EditorialPost:
    for key, value in fields.items():
        setattr(post, key, value)
    db.commit()
    db.refresh(post)
    return post


def delete(db: Session, post: EditorialPost) -> None:
    db.delete(post)
    db.commit()


# --- Комментарии ---

def add_comment(
    db: Session,
    *,
    post_id: int,
    target: EditorialCommentTarget,
    author_id: int,
    body: str,
    parent_id: int | None,
) -> EditorialComment:
    comment = EditorialComment(
        post_id=post_id,
        target=target,
        author_id=author_id,
        body=body,
        parent_id=parent_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def get_comment(db: Session, comment_id: int) -> EditorialComment | None:
    return db.get(EditorialComment, comment_id)


def update_comment(db: Session, comment: EditorialComment, fields: dict) -> EditorialComment:
    for key, value in fields.items():
        setattr(comment, key, value)
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, comment: EditorialComment) -> None:
    db.delete(comment)
    db.commit()
