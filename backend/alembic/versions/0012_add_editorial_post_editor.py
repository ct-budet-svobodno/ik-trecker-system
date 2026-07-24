"""add editorial_posts.editor_id

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch-режим: SQLite не умеет ALTER с добавлением FK-констрейнта.
    with op.batch_alter_table("editorial_posts") as batch_op:
        batch_op.add_column(sa.Column("editor_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_editorial_posts_editor_id_users", "users", ["editor_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("editorial_posts") as batch_op:
        batch_op.drop_constraint("fk_editorial_posts_editor_id_users", type_="foreignkey")
        batch_op.drop_column("editor_id")
