"""user_profiles.photo{1,2}_file_id: Telegram ids of the profile photos

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_profiles") as batch:
        batch.add_column(sa.Column("photo1_file_id", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("photo2_file_id", sa.String(length=256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_column("photo2_file_id")
        batch.drop_column("photo1_file_id")
