"""Track Welcome Book reading progress per user and edition."""

from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "welcome_book_progress",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("max_page", sa.Integer(), nullable=False),
        sa.Column("first_opened_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("welcome_book_progress")
