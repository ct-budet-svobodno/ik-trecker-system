"""users: add telegram_id, telegram_username

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite не умеет ALTER с ограничениями — добавляем колонки через batch.
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("telegram_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("telegram_username", sa.String(length=64), nullable=True))
        batch.create_unique_constraint("uq_users_telegram_id", ["telegram_id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_telegram_id", type_="unique")
        batch.drop_column("telegram_username")
        batch.drop_column("telegram_id")
