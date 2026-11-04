"""create surveys, survey_recipients, survey_responses

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "surveys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "OPEN", "CLOSED", name="surveystatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_surveys_author_id", "surveys", ["author_id"])
    op.create_table(
        "survey_recipients",
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("survey_id", "user_id", name="uq_survey_responses_survey_user"),
    )
    op.create_index("ix_survey_responses_survey_id", "survey_responses", ["survey_id"])


def downgrade() -> None:
    op.drop_table("survey_responses")
    op.drop_table("survey_recipients")
    op.drop_index("ix_surveys_author_id", table_name="surveys")
    op.drop_table("surveys")
