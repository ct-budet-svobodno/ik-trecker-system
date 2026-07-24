"""leadership_tasks: add span (end_date, position_end) and color

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite не умеет ALTER COLUMN — добавляем колонки через batch.
    with op.batch_alter_table("leadership_tasks") as batch:
        batch.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column(
                "position_end",
                sa.Enum(
                    "chairman",
                    "secretary",
                    "first_deputy",
                    "brand_manager",
                    name="leadershipposition",
                ),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("color", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("leadership_tasks") as batch:
        batch.drop_column("color")
        batch.drop_column("position_end")
        batch.drop_column("end_date")
