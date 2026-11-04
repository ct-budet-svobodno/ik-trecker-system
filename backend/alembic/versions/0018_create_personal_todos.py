"""create personal_todos table

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personal_todos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_personal_todos_user_id", "personal_todos", ["user_id"])
    op.create_index("ix_personal_todos_date", "personal_todos", ["date"])


def downgrade() -> None:
    op.drop_index("ix_personal_todos_date", table_name="personal_todos")
    op.drop_index("ix_personal_todos_user_id", table_name="personal_todos")
    op.drop_table("personal_todos")
