"""create zavod boards, nodes and edges

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zavod_boards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "zavod_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        # SQLAlchemy кладёт в колонку имена элементов enum (TODO), а не значения
        # (todo) — в ранних миграциях указаны значения, но на SQLite это ни на что
        # не влияет: CHECK-констрейнт не создаётся, колонка обычный VARCHAR.
        sa.Column(
            "status",
            sa.Enum("TODO", "IN_PROGRESS", "DONE", name="zavodnodestatus"),
            nullable=False,
        ),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["board_id"], ["zavod_boards.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zavod_nodes_board_id", "zavod_nodes", ["board_id"])

    op.create_table(
        "zavod_node_assignees",
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["zavod_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("node_id", "user_id"),
    )

    op.create_table(
        "zavod_edges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["board_id"], ["zavod_boards.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["zavod_nodes.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["zavod_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zavod_edges_board_id", "zavod_edges", ["board_id"])
    op.create_index("ix_zavod_edges_source_id", "zavod_edges", ["source_id"])
    op.create_index("ix_zavod_edges_target_id", "zavod_edges", ["target_id"])


def downgrade() -> None:
    op.drop_index("ix_zavod_edges_target_id", table_name="zavod_edges")
    op.drop_index("ix_zavod_edges_source_id", table_name="zavod_edges")
    op.drop_index("ix_zavod_edges_board_id", table_name="zavod_edges")
    op.drop_table("zavod_edges")
    op.drop_table("zavod_node_assignees")
    op.drop_index("ix_zavod_nodes_board_id", table_name="zavod_nodes")
    op.drop_table("zavod_nodes")
    op.drop_table("zavod_boards")
