"""Заполняет dev-БД демо-сотрудниками и задачами для визуальной проверки. Запускать после
`alembic upgrade head` и `create_admin`:

    python -m scripts.seed_demo_tasks
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.task import TaskPriority, TaskStatus
from app.models.user import UserRole
from app.repositories import direction_repository, task_repository, user_repository
from app.schemas.user import UserCreate
from app.services import user_service

DEMO_PASSWORD = "demo12345"

DEMO_USERS = [
    # (username, full_name, role)
    ("m.ivanova", "Маша Иванова", UserRole.EMPLOYEE),
    ("a.sokolov", "Артём Соколов", UserRole.EMPLOYEE),
    ("l.petrova", "Лиза Петрова", UserRole.EMPLOYEE),
    ("d.k", "Денис К.", UserRole.EMPLOYEE),
    ("n.orlov", "Никита Орлов", UserRole.EMPLOYEE),
    ("a.golubeva", "Аня Голубева", UserRole.EMPLOYEE),
    ("i.manaev", "Игорь Манаев", UserRole.MANAGER),
]

# (title, description, направление, priority, status, assignee_username|None, due_date)
DEMO_TASKS = [
    (
        "Афиша к фестивалю «ИК-Осень»",
        "Сделать макет афиши А2 в фирменном стиле, 2 варианта компоновки. Передать в печать до конца недели.",
        "Дизайн", TaskPriority.HIGH, TaskStatus.IN_PROGRESS, "m.ivanova", date(2027, 5, 22),
    ),
    (
        "Обновить раздел «Команда» на сайте",
        "Поднять данные из формы, заменить фото и должности, проверить адаптив на мобилке.",
        "ЦТ", TaskPriority.MEDIUM, TaskStatus.TODO, "a.sokolov", date(2027, 5, 25),
    ),
    (
        "Пост в Telegram о наборе в актив",
        "Текст 600-800 знаков + 3 карточки. Согласовать с координатором перед публикацией.",
        "СМИ", TaskPriority.MEDIUM, TaskStatus.IN_REVIEW, "l.petrova", date(2027, 5, 18),
    ),
    (
        "Съёмка с открытия выставки",
        "Загрузить отобранные кадры в общий диск, обработать топ-10 для соцсетей.",
        "Фото", TaskPriority.LOW, TaskStatus.DONE, "d.k", date(2027, 5, 14),
    ),
    (
        "Райдер и расстановка на «Весенний концерт»",
        "Согласовать со звуком, собрать тех. райдер, отправить площадке к понедельнику.",
        "Прод", TaskPriority.HIGH, TaskStatus.IN_PROGRESS, "n.orlov", date(2027, 5, 20),
    ),
    (
        "Программа дебатов для первокурсников",
        "Составить сетку из 4 раундов, темы и регламент. Подобрать модераторов.",
        "НВК", TaskPriority.MEDIUM, TaskStatus.TODO, "a.golubeva", date(2027, 5, 28),
    ),
    (
        "Форма регистрации на школу актива",
        "Подключить валидацию полей, отправку в Google Sheets, страница «спасибо».",
        "ЦТ", TaskPriority.HIGH, TaskStatus.IN_REVIEW, "a.sokolov", date(2027, 5, 19),
    ),
    (
        "Бейджи для оргкомитета",
        "Шаблон под 4 роли, цветовая маркировка по направлению. PDF на печать.",
        "Дизайн", TaskPriority.LOW, TaskStatus.TODO, None, date(2027, 5, 30),
    ),
    (
        "Бюджет на следующий квартал",
        "Свести смету по направлениям, согласовать с правлением. Личная задача руководителя — "
        "не должна быть видна сотрудникам.",
        "Прод", TaskPriority.HIGH, TaskStatus.TODO, "i.manaev", date(2027, 6, 10),
    ),
]


def main() -> None:
    db = SessionLocal()
    try:
        admin = user_repository.get_by_username(db, "admin")
        if admin is None:
            print("Сначала создайте админа: python -m scripts.create_admin")
            return

        users_by_username = {}
        for username, full_name, role in DEMO_USERS:
            existing = user_repository.get_by_username(db, username)
            if existing is not None:
                users_by_username[username] = existing
                continue
            user = user_service.create_user(
                db,
                UserCreate(username=username, password=DEMO_PASSWORD, full_name=full_name, role=role),
            )
            users_by_username[username] = user
            print(f"Создан пользователь {username} ({role.value})")

        directions_by_code = {d.short_code: d for d in direction_repository.list_all(db)}

        created_count = 0
        for title, description, direction_code, priority, status, assignee_username, due_date in DEMO_TASKS:
            direction = directions_by_code.get(direction_code)
            if direction is None:
                print(f"Направление '{direction_code}' не найдено, пропускаю задачу '{title}'")
                continue
            assignee = users_by_username.get(assignee_username) if assignee_username else None
            task = task_repository.create(
                db,
                title=title,
                description=description,
                direction_id=direction.id,
                priority=priority,
                assignee_id=assignee.id if assignee else None,
                due_date=due_date,
                created_by_id=admin.id,
            )
            if status != TaskStatus.TODO:
                task_repository.update_fields(db, task, {"status": status})
            created_count += 1

        print(f"Готово: создано {created_count} демо-задач. Пароль для демо-аккаунтов: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
