"""leadership_tasks: add position, make direction_id nullable

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite не умеет ALTER COLUMN — пересоздаём таблицу через batch.
    with op.batch_alter_table("leadership_tasks") as batch:
        batch.add_column(
            sa.Column(
                "position",
                sa.Enum("chairman", "secretary", "first_deputy", name="leadershipposition"),
                nullable=True,
            )
        )
        batch.alter_column("direction_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("leadership_tasks") as batch:
        batch.alter_column("direction_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("position")
