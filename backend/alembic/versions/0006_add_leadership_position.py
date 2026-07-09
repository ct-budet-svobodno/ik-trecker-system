"""add leadership_position to users

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "leadership_position",
            sa.Enum("chairman", "secretary", "first_deputy", name="leadershipposition"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "leadership_position")
