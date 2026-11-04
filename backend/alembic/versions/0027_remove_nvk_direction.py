"""remove the НВК direction when nothing uses it

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-21

Направление НВК убрали. Удаляем, только если на нём нет задач и руководителей
(так на проде); где оно ещё занято (тестовые данные в dev) — не трогаем.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM directions WHERE short_code = 'НВК' "
        "AND NOT EXISTS (SELECT 1 FROM tasks WHERE tasks.direction_id = directions.id) "
        "AND NOT EXISTS (SELECT 1 FROM direction_heads h WHERE h.direction_id = directions.id) "
        "AND NOT EXISTS (SELECT 1 FROM user_profiles p WHERE p.direction_id = directions.id)"
    )


def downgrade() -> None:
    # Удалённое направление не восстанавливаем — при надобности его заводят заново.
    pass
