"""create sea_battle_games table

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sea_battle_games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column(
            "host_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "guest_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("vs_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "status",
            sa.Enum(
                "WAITING", "READY_CHECK", "PLACING", "PLAYING", "FINISHED", "CANCELLED",
                name="seabattlestatus",
            ),
            nullable=False,
        ),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ready_deadline", sa.DateTime(), nullable=True),
        sa.Column("host_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("guest_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sea_battle_games_code", "sea_battle_games", ["code"], unique=True)
    op.create_index("ix_sea_battle_games_host_id", "sea_battle_games", ["host_id"])
    op.create_index("ix_sea_battle_games_guest_id", "sea_battle_games", ["guest_id"])


def downgrade() -> None:
    op.drop_index("ix_sea_battle_games_guest_id", table_name="sea_battle_games")
    op.drop_index("ix_sea_battle_games_host_id", table_name="sea_battle_games")
    op.drop_index("ix_sea_battle_games_code", table_name="sea_battle_games")
    op.drop_table("sea_battle_games")
