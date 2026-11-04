"""add users.is_activist and users.direction_id

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_activist", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # SQLite: alembic не умеет add_column с внешним ключом, а сам ALTER умеет.
    op.execute("ALTER TABLE users ADD COLUMN direction_id INTEGER REFERENCES directions (id) ON DELETE SET NULL")
    # Кто заполнял анкету (в мини-аппе или в боте) — в активе, направление — из анкеты.
    op.execute(
        """
        UPDATE users SET
          is_activist = 1,
          direction_id = (SELECT p.direction_id FROM user_profiles p WHERE p.user_id = users.id)
        WHERE id IN (SELECT user_id FROM user_profiles)
        """
    )


def downgrade() -> None:
    op.drop_column("users", "direction_id")
    op.drop_column("users", "is_activist")
