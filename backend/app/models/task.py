import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.direction import Direction
from app.models.user import User


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), nullable=False, default=TaskStatus.TODO)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # У личного поручения направления нет.
    direction_id: Mapped[int | None] = mapped_column(ForeignKey("directions.id"), nullable=True)
    # Личное поручение руководства: видят автор, исполнители, админы и секретарь.
    # См. task_repository.list_visible_for.
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_checklist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # У поручения исполнителей может быть несколько — они в task_assignees,
    # здесь первый из них (для карточек и старых клиентов). Статус поручения —
    # сводный по исполнителям (см. task_service.overall_status).
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Когда автор последний раз напоминал о поручении (UTC) — для паузы между напоминаниями.
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    direction: Mapped[Direction | None] = relationship(foreign_keys=[direction_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])

    assignees: Mapped[list["TaskAssignee"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskAssignee.id"
    )
    comments: Mapped[list["TaskComment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskComment.id"
    )


class TaskAssignee(Base):
    """Исполнитель личного поручения со своим статусом: каждый ведёт свою часть,
    автор видит, кто уже сделал."""

    __tablename__ = "task_assignees"
    __table_args__ = (UniqueConstraint("task_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), nullable=False, default=TaskStatus.TODO)

    task: Mapped[Task] = relationship(back_populates="assignees")
    user: Mapped[User] = relationship()


class TaskComment(Base):
    """Комментарий к ТЗ или поручению. Ответы — через parent_id (один уровень)."""

    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_comments.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[Task] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()
