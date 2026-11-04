"""create task_assignees: several assignees for a private task

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_assignees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum("TODO", "IN_PROGRESS", "IN_REVIEW", "DONE", name="taskstatus"),
            nullable=False,
        ),
        sa.UniqueConstraint("task_id", "user_id"),
    )
    op.create_index("ix_task_assignees_task_id", "task_assignees", ["task_id"])
    op.create_index("ix_task_assignees_user_id", "task_assignees", ["user_id"])
    # Уже выданные поручения: их единственный исполнитель со статусом поручения.
    op.execute(
        "INSERT INTO task_assignees (task_id, user_id, status) "
        "SELECT id, assignee_id, status FROM tasks "
        "WHERE is_private = 1 AND assignee_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_task_assignees_user_id", table_name="task_assignees")
    op.drop_index("ix_task_assignees_task_id", table_name="task_assignees")
    op.drop_table("task_assignees")
