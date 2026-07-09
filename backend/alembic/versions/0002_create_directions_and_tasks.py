"""create directions and tasks tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIRECTIONS = [
    # (short_code, name, color, sort_order)
    ("ЦТ", "Цифровые технологии", "violet", 0),
    ("Прод", "Продакшен", "blue", 1),
    ("Дизайн", "Дизайн", "pink", 2),
    ("Фото", "Фото", "green", 3),
    ("СМИ", "СМИ", "orange", 4),
    ("НВК", "НВК", "cyan", 5),
]


def upgrade() -> None:
    op.create_table(
        "directions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("short_code", sa.String(length=16), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_directions_short_code", "directions", ["short_code"], unique=True)

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.Enum("todo", "in_progress", "in_review", "done", name="taskstatus"),
            nullable=False,
            server_default="todo",
        ),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", name="taskpriority"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("direction_id", sa.Integer(), sa.ForeignKey("directions.id"), nullable=False),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    directions_table = sa.table(
        "directions",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("short_code", sa.String()),
        sa.column("color", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(
        directions_table,
        [
            {"short_code": code, "name": name, "color": color, "sort_order": order}
            for code, name, color, order in DIRECTIONS
        ],
    )


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_index("ix_directions_short_code", table_name="directions")
    op.drop_table("directions")
