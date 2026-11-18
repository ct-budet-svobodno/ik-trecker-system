"""Telegram polls with recipient snapshots and personal votes."""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("telegram_polls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table("telegram_poll_recipients",
        sa.Column("poll_id", sa.Integer(), sa.ForeignKey("telegram_polls.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger()),
        sa.Column("full_name", sa.String(128), nullable=False),
        sa.Column("telegram_username", sa.String(64)),
        sa.Column("delivery", sa.String(16), nullable=False),
        sa.Column("choice", sa.Integer()),
        sa.Column("voted_at", sa.DateTime()),
    )


def downgrade():
    op.drop_table("telegram_poll_recipients")
    op.drop_table("telegram_polls")
