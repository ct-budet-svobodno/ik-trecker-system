"""create leadership_tasks table

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leadership_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("todo", "done", name="leadershiptaskstatus"),
            nullable=False,
            server_default="todo",
        ),
        sa.Column("direction_id", sa.Integer(), sa.ForeignKey("directions.id"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_leadership_tasks_date", "leadership_tasks", ["date"]
    )


def downgrade() -> None:
    op.drop_index("ix_leadership_tasks_date", table_name="leadership_tasks")
    op.drop_table("leadership_tasks")
