"""Allow every tracker user to issue checklist tasks.

Revision ID: 0038
Revises: 0037
"""
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("can_issue_checklists")


def downgrade() -> None:
    import sqlalchemy as sa

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("can_issue_checklists", sa.Boolean(), nullable=False, server_default=sa.false()))
