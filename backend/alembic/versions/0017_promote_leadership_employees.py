"""promote employees holding a leadership position to manager

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Держатель должности руководства должен быть минимум manager, иначе ему
    # закрыт таймлайн руководства. Раньше PATCH /users мог сохранить должность
    # вместе с ролью employee — чиним уже записанные строки.
    op.execute(
        "UPDATE users SET role = 'MANAGER' "
        "WHERE role = 'EMPLOYEE' AND leadership_position IS NOT NULL"
    )


def downgrade() -> None:
    # Исправление данных — откатывать нечего.
    pass
