"""users.direction_id -> direction_members (several directions per user)

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "direction_members",
        sa.Column("direction_id", sa.Integer(), sa.ForeignKey("directions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )
    op.execute(
        "INSERT INTO direction_members (direction_id, user_id) "
        "SELECT direction_id, id FROM users WHERE direction_id IS NOT NULL"
    )
    op.execute("ALTER TABLE users DROP COLUMN direction_id")


def downgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN direction_id INTEGER REFERENCES directions (id) ON DELETE SET NULL")
    op.execute(
        "UPDATE users SET direction_id = "
        "(SELECT MIN(direction_id) FROM direction_members m WHERE m.user_id = users.id)"
    )
    op.drop_table("direction_members")
