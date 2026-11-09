"""allow selected activists to issue checklist tasks

Revision ID: 0036
Revises: 0035
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("can_issue_checklists", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("is_checklist", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("is_checklist")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("can_issue_checklists")
