"""create editorial_posts and editorial_comments

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "editorial_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("format", sa.String(length=100), nullable=True),
        sa.Column("brief", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference", sa.String(length=500), nullable=True),
        sa.Column("writer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("designer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "text_status",
            sa.Enum("empty", "draft", "review", "fixes", "ready", name="editorialstatus"),
            nullable=False,
            server_default="empty",
        ),
        sa.Column("figma_url", sa.String(length=500), nullable=True),
        sa.Column("design_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "design_status",
            sa.Enum("empty", "draft", "review", "fixes", "ready", name="editorialstatus"),
            nullable=False,
            server_default="empty",
        ),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_editorial_posts_date", "editorial_posts", ["date"])

    op.create_table(
        "editorial_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("editorial_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target",
            sa.Enum("text", "design", name="editorialcommenttarget"),
            nullable=False,
        ),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "parent_id", sa.Integer(), sa.ForeignKey("editorial_comments.id"), nullable=True
        ),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_editorial_comments_post_id", "editorial_comments", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_editorial_comments_post_id", table_name="editorial_comments")
    op.drop_table("editorial_comments")
    op.drop_index("ix_editorial_posts_date", table_name="editorial_posts")
    op.drop_table("editorial_posts")
