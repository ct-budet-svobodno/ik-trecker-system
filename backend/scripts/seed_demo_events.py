"""Заполняет dev-БД демо-мероприятиями для визуальной проверки календаря. Запускать после
`create_admin`:

    python -m scripts.seed_demo_events
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.repositories import event_repository, user_repository
from app.schemas.event import EventCreate
from app.services import event_service

DEMO_EVENTS = [
    (
        "Весенний концерт",
        "Большой концерт на главной площадке. Нужны звук, свет, рассадка.",
        "Городской ДК",
        datetime(2027, 5, 20, 19, 0),
        datetime(2027, 5, 20, 22, 0),
    ),
    (
        "Фестиваль «ИК-Осень»",
        "Главное ежегодное событие комитета — выставки, мастер-классы, концерт.",
        "Главный корпус",
        datetime(2027, 9, 12, 10, 0),
        datetime(2027, 9, 12, 20, 0),
    ),
    (
        "Открытие выставки",
        "Открытие фотовыставки по итогам года.",
        "Холл 2 этажа",
        datetime(2027, 5, 14, 15, 0),
        None,
    ),
    (
        "Встреча координаторов",
        "Еженедельная синхронизация направлений.",
        None,
        datetime(2027, 3, 3, 10, 0),
        datetime(2027, 3, 3, 11, 0),
    ),
]


def main() -> None:
    db = SessionLocal()
    try:
        admin = user_repository.get_by_username(db, "admin")
        if admin is None:
            print("Сначала создайте админа: python -m scripts.create_admin")
            return

        existing_titles = {event.title for event in event_repository.list_all(db)}
        created_count = 0
        for title, description, location, start_at, end_at in DEMO_EVENTS:
            if title in existing_titles:
                continue
            event_service.create_event(
                db,
                EventCreate(
                    title=title,
                    description=description,
                    location=location,
                    start_at=start_at,
                    end_at=end_at,
                ),
                created_by=admin,
            )
            created_count += 1

        print(f"Готово: создано {created_count} демо-мероприятий.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
