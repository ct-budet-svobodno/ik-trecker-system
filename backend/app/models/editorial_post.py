import datetime
import enum

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class EditorialStatus(str, enum.Enum):
    """Статус трека (текст/дизайн) в посте Редакции."""

    EMPTY = "empty"  # ещё не начато
    DRAFT = "draft"  # черновик (автор работает)
    REVIEW = "review"  # на проверке у редактора
    FIXES = "fixes"  # вернули на правки
    READY = "ready"  # принято


class EditorialCommentTarget(str, enum.Enum):
    TEXT = "text"
    DESIGN = "design"


class EditorialPost(Base):
    """Пост в SMM-календаре Редакции. Отдельная сущность, не обычная задача —
    в общую доска `GET /tasks` не попадает."""

    __tablename__ = "editorial_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brief: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Роли. Заполняются самим участником («проставился») или редактором.
    writer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    designer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Текстовый трек.
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_status: Mapped[EditorialStatus] = mapped_column(
        Enum(EditorialStatus), nullable=False, default=EditorialStatus.EMPTY
    )

    # Дизайн-трек.
    figma_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    design_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    design_status: Mapped[EditorialStatus] = mapped_column(
        Enum(EditorialStatus), nullable=False, default=EditorialStatus.EMPTY
    )

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    writer: Mapped[User | None] = relationship(foreign_keys=[writer_id])
    designer: Mapped[User | None] = relationship(foreign_keys=[designer_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    comments: Mapped[list["EditorialComment"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="EditorialComment.created_at",
    )


class EditorialComment(Base):
    """Комментарий-правка к тексту или дизайну поста. Треды — через parent_id."""

    __tablename__ = "editorial_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("editorial_posts.id", ondelete="CASCADE"), nullable=False
    )
    target: Mapped[EditorialCommentTarget] = mapped_column(
        Enum(EditorialCommentTarget), nullable=False
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("editorial_comments.id"), nullable=True
    )
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    post: Mapped["EditorialPost"] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(foreign_keys=[author_id])
