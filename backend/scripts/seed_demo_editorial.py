"""Демо-данные для «Редакции» (SMM-календарь): пара участников с флагом
is_editorial и несколько постов на текущую неделю. Запускать после
seed_demo_leadership (там назначаются руководители СМИ/Дизайна — ревьюеры):

    python -m scripts.seed_demo_editorial
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.repositories import editorial_post_repository, user_repository

# Участники Редакции (username) — им выставим is_editorial.
MEMBERS = ["a.sokolov", "d.k", "n.orlov", "a.golubeva"]

# Демо-посты: (смещение дней от понедельника, название, формат, суть, райтер, дизайнер).
SAMPLE = [
    (0, "Карусель про набор", "карусель", "Объявляем набор в команду, 6 слайдов", "a.sokolov", "d.k"),
    (2, "Reels: закулисье съёмки", "reels", "Динамичный ролик со съёмочного дня", None, "n.orlov"),
    (4, "СЗ: анонс дебатов", "СЗ", "Социальный заказ — анонс программы дебатов", "a.golubeva", None),
]


def main() -> None:
    db = SessionLocal()
    try:
        admin = user_repository.get_by_username(db, "admin")
        if admin is None:
            print("Сначала создайте админа: python -m scripts.create_admin")
            return

        # 1. Флаг Редакции.
        for username in MEMBERS:
            user = user_repository.get_by_username(db, username)
            if user is None:
                print(f"Пропуск участника {username}: нет пользователя")
                continue
            user.is_editorial = True
            print(f"Редакция -> {username}")
        db.commit()

        # 2. Демо-посты на текущую неделю (если их ещё нет).
        monday = date.today() - timedelta(days=date.today().weekday())
        existing = editorial_post_repository.list_in_range(db, monday, monday + timedelta(days=6))
        if existing:
            print(f"Посты на этой неделе уже есть ({len(existing)}) — пропускаю сидинг постов.")
        else:
            created = 0
            for day_offset, title, fmt, brief, writer, designer in SAMPLE:
                post = editorial_post_repository.create(
                    db,
                    date=monday + timedelta(days=day_offset),
                    title=title,
                    format=fmt,
                    brief=brief,
                    reference=None,
                    created_by_id=admin.id,
                )
                fields = {}
                if writer:
                    w = user_repository.get_by_username(db, writer)
                    if w:
                        fields["writer_id"] = w.id
                if designer:
                    d = user_repository.get_by_username(db, designer)
                    if d:
                        fields["designer_id"] = d.id
                if fields:
                    editorial_post_repository.update_fields(db, post, fields)
                created += 1
            print(f"Создано демо-постов Редакции: {created}")

        print("Готово.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
