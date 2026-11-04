"""create bunker_games and bunker_players tables

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bunker_games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column(
            "host_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum("WAITING", "PLAYING", "FINISHED", "CANCELLED", name="bunkerstatus"),
            nullable=False,
        ),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("phase_started_at", sa.DateTime(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bunker_games_code", "bunker_games", ["code"], unique=True)
    op.create_index("ix_bunker_games_host_id", "bunker_games", ["host_id"])
    op.create_table(
        "bunker_players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "game_id", sa.Integer(), sa.ForeignKey("bunker_games.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("seat", sa.Integer(), nullable=False),
        sa.UniqueConstraint("game_id", "user_id"),
    )
    op.create_index("ix_bunker_players_game_id", "bunker_players", ["game_id"])
    op.create_index("ix_bunker_players_user_id", "bunker_players", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_bunker_players_user_id", table_name="bunker_players")
    op.drop_index("ix_bunker_players_game_id", table_name="bunker_players")
    op.drop_table("bunker_players")
    op.drop_index("ix_bunker_games_host_id", table_name="bunker_games")
    op.drop_index("ix_bunker_games_code", table_name="bunker_games")
    op.drop_table("bunker_games")
