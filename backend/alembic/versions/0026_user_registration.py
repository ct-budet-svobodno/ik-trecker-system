"""users.registration_status + user_profiles: sign-up from the mini app

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "registration_status",
                sa.Enum("APPROVED", "PENDING", "REJECTED", name="registrationstatus"),
                nullable=False,
                server_default="APPROVED",
            )
        )
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("birthday", sa.Date(), nullable=False),
        sa.Column(
            "direction_id",
            sa.Integer(),
            sa.ForeignKey("directions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("study_group", sa.String(length=64), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("clothes_size", sa.String(length=16), nullable=False),
        sa.Column("other_units", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("photo1", sa.String(length=128), nullable=False),
        sa.Column("photo2", sa.String(length=128), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("registration_status")
