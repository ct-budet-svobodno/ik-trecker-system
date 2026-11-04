"""create broadcasts table

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("buttons", sa.JSON(), nullable=False),
        sa.Column("status", sa.Enum("SENDING", "DONE", name="broadcaststatus"), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broadcasts_author_id", "broadcasts", ["author_id"])


def downgrade() -> None:
    op.drop_index("ix_broadcasts_author_id", table_name="broadcasts")
    op.drop_table("broadcasts")
