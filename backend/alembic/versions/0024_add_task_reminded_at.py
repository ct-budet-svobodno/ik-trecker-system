"""add tasks.reminded_at: last reminder about a private task

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("reminded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("reminded_at")
