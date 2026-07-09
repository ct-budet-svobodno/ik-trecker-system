"""Демо-данные для «Таймлайна руководства»: руководители направлений, тройка и
несколько записей на текущую неделю. Запускать после seed_demo_tasks:

    python -m scripts.seed_demo_leadership
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.leadership_task import LeadershipTaskStatus
from app.models.user import LeadershipPosition
from app.repositories import (
    direction_repository,
    leadership_task_repository,
    user_repository,
)
from app.services import direction_service, user_service

# Руководитель каждого направления (по short_code -> username).
HEADS = {
    "ЦТ": "a.sokolov",
    "Дизайн": "m.ivanova",
    "СМИ": "l.petrova",
    "Фото": "d.k",
    "Прод": "n.orlov",
    "НВК": "a.golubeva",
}

# Тройка (должность -> username).
TROIKA = {
    LeadershipPosition.CHAIRMAN: "i.manaev",
    LeadershipPosition.SECRETARY: "m.ivanova",
    LeadershipPosition.FIRST_DEPUTY: "a.sokolov",
}

# Демо-записи таймлайна: (short_code, смещение дней от понедельника недели, текст, выполнено).
SAMPLE = [
    ("ЦТ", 0, "Создание чата направления", True),
    ("Дизайн", 1, "Создаём чат экс-руководителей в тг", False),
    ("Дизайн", 2, "В ЗГ Дизайна добавить контакты руковода 67", True),
    ("СМИ", 1, "Составлен СММ-план на июль", False),
    ("СМИ", 4, "Список тех, с кем можно заколлабиться", False),
    ("Прод", 0, "Создание чата направления", True),
    ("Фото", 0, "Создание чата направления", True),
    ("НВК", 3, "Подготовить программу дебатов", False),
]


def main() -> None:
    db = SessionLocal()
    try:
        admin = user_repository.get_by_username(db, "admin")
        if admin is None:
            print("Сначала создайте админа: python -m scripts.create_admin")
            return

        directions = {d.short_code: d for d in direction_repository.list_all(db)}

        # 1. Руководители направлений (повышает до manager).
        for code, username in HEADS.items():
            direction = directions.get(code)
            user = user_repository.get_by_username(db, username)
            if direction is None or user is None:
                print(f"Пропуск head {code}/{username}: нет направления или пользователя")
                continue
            direction_service.set_heads(db, direction, [user.id])
            print(f"Руководитель {code} -> {username}")

        # 2. Тройка.
        for position, username in TROIKA.items():
            user = user_repository.get_by_username(db, username)
            if user is None:
                print(f"Пропуск тройки {position.value}: нет пользователя {username}")
                continue
            user_service.set_leadership_position(db, user, position)
            print(f"{position.value} -> {username}")

        # 3. Демо-записи на текущую неделю (если их ещё нет).
        monday = date.today() - timedelta(days=date.today().weekday())
        existing = leadership_task_repository.list_in_range(
            db, monday, monday + timedelta(days=6)
        )
        if existing:
            print(f"Записи на этой неделе уже есть ({len(existing)}) — пропускаю сидинг записей.")
        else:
            created = 0
            for code, day_offset, title, done in SAMPLE:
                direction = directions.get(code)
                if direction is None:
                    continue
                task = leadership_task_repository.create(
                    db,
                    title=title,
                    direction_id=direction.id,
                    position=None,
                    date=monday + timedelta(days=day_offset),
                    status=LeadershipTaskStatus.TODO,
                    created_by_id=admin.id,
                )
                if done:
                    leadership_task_repository.update_fields(
                        db, task, {"status": LeadershipTaskStatus.DONE}
                    )
                created += 1
            print(f"Создано демо-записей таймлайна: {created}")

        print("Готово.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
