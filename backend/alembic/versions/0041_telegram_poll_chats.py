"""Choose a group chat for Telegram polls."""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("telegram_poll_chats",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("title", sa.String(255), nullable=False),
    )
    op.add_column("telegram_polls", sa.Column("chat_id", sa.BigInteger()))
    op.add_column("telegram_polls", sa.Column("chat_title", sa.String(255)))
    op.add_column("telegram_polls", sa.Column("chat_delivery", sa.String(16)))


def downgrade():
    op.drop_column("telegram_polls", "chat_delivery")
    op.drop_column("telegram_polls", "chat_title")
    op.drop_column("telegram_polls", "chat_id")
    op.drop_table("telegram_poll_chats")
