"""create checklist_cards table

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checklist_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("image_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.Enum("DRAFT", "SENT", "FAILED", name="checkliststatus"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("checklist_cards")
