"""Тестовые аккаунты под каждую роль — чтобы проверять трекер глазами разных людей.
Только для локальной разработки. Запускать после seed_demo_tasks (нужны направления):

    python -m scripts.seed_test_roles

Пароль у всех — test12345. Тот же список зашит в DevRoleSwitcher на фронте
(виден только в dev-сборке) — при правке держать оба места в согласии.
Повторный запуск ничего не дублирует: данные создаются только для новых аккаунтов.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.leadership_task import LeadershipTaskStatus
from app.models.task import TaskPriority, TaskStatus
from app.models.user import LeadershipPosition, UserRole
from app.repositories import (
    direction_repository,
    leadership_task_repository,
    personal_todo_repository,
    task_repository,
    user_repository,
)
from app.schemas.user import UserCreate
from app.services import direction_service, user_service

TEST_PASSWORD = "test12345"

# (username, full_name, должность, руководит направлением, флаг Редакции)
TEST_USERS = [
    ("t.chairman", "Председатель Тестовый", LeadershipPosition.CHAIRMAN, None, False),
    ("t.secretary", "Секретарь Тестовый", LeadershipPosition.SECRETARY, None, False),
    ("t.head", "Руководитель НВК Тестовый", None, "НВК", False),
    ("t.activist", "Активист Тестовый", None, None, False),
    ("t.editorial", "Активист Редакции Тестовый", None, None, True),
]


def _ensure_user(db, username, full_name):
    """Вернуть (пользователь, создан_ли_сейчас)."""
    user = user_repository.get_by_username(db, username)
    if user is not None:
        return user, False
    user = user_service.create_user(
        db,
        UserCreate(username=username, password=TEST_PASSWORD, full_name=full_name, role=UserRole.EMPLOYEE),
    )
    return user, True


def main() -> None:
    db = SessionLocal()
    try:
        directions = {d.short_code: d for d in direction_repository.list_all(db)}
        if not directions:
            print("Нет направлений — сначала python -m scripts.seed_demo_tasks")
            return

        users, created = {}, set()
        for username, full_name, position, head_of, editorial in TEST_USERS:
            user, is_new = _ensure_user(db, username, full_name)
            users[username] = user
            if is_new:
                created.add(username)
            if position is not None:
                # Должность единоличная: заберёт её у демо-пользователя.
                user_service.set_leadership_position(db, user, position)
            if head_of and head_of in directions:
                direction = directions[head_of]
                ids = [h.id for h in direction.heads]
                if user.id not in ids:
                    direction_service.set_heads(db, direction, ids + [user.id])
            if editorial and not user.is_editorial:
                user_repository.update(db, user, is_editorial=True)
            if username in ("t.activist", "t.editorial"):
                user_repository.update(
                    db, user,
                    is_activist=True,
                    can_issue_checklists=username == "t.activist",
                )
            print(f"{'создан' if is_new else 'есть   '} {username}")

        admin, is_new = _ensure_user(db, "t.admin", "Администратор Тестовый")
        user_repository.update(db, admin, role=UserRole.ADMIN)
        print(f"{'создан' if is_new else 'есть   '} t.admin")

        today = date.today()
        chairman, activist, head = users["t.chairman"], users["t.activist"], users["t.head"]
        nvk = directions.get("НВК")

        if "t.activist" in created and nvk is not None:
            # Задачи активиста во всех статусах + одна просроченная.
            for title, status, priority, due in [
                ("Собрать список спикеров для дебатов", TaskStatus.TODO, TaskPriority.HIGH, today - timedelta(days=2)),
                ("Подготовить анонс встречи", TaskStatus.IN_PROGRESS, TaskPriority.MEDIUM, today + timedelta(days=1)),
                ("Отчёт по прошлому мероприятию", TaskStatus.IN_REVIEW, TaskPriority.LOW, today + timedelta(days=5)),
                ("Забронировать аудиторию", TaskStatus.DONE, TaskPriority.MEDIUM, today - timedelta(days=3)),
            ]:
                task = task_repository.create(
                    db, title=title, description="Тестовая задача для проверки ролей.",
                    direction_id=nvk.id, priority=priority, assignee_id=activist.id,
                    due_date=due, created_by_id=head.id,
                )
                if status != TaskStatus.TODO:
                    task_repository.update_fields(db, task, {"status": status})
            # Личное поручение от председателя: видят он, активист, админы и секретарь.
            task_repository.create(
                db, title="Личное поручение: позвонить партнёру", description="Видно только автору, исполнителю, админам и секретарю.",
                direction_id=None, priority=TaskPriority.HIGH, assignee_id=activist.id,
                due_date=today + timedelta(days=2), created_by_id=chairman.id, is_private=True,
            )
            for title in ("Проверить почту направления", "Ответить в чате актива"):
                personal_todo_repository.create(db, user_id=activist.id, day=today, title=title)
            print("Задачи, поручение и «Мой день» для t.activist")

        if "t.head" in created and nvk is not None:
            task_repository.create(
                db, title="Согласовать бюджет НВК", description="Тестовая задача руководителя направления.",
                direction_id=nvk.id, priority=TaskPriority.MEDIUM, assignee_id=head.id,
                due_date=today + timedelta(days=3), created_by_id=chairman.id,
            )
            print("Задача для t.head")

        if "t.chairman" in created:
            leadership_task_repository.create(
                db, title="Встреча с ректоратом", direction_id=None,
                position=LeadershipPosition.CHAIRMAN, is_editorial=False, date=today,
                status=LeadershipTaskStatus.TODO, created_by_id=chairman.id,
            )
            print("Запись таймлайна для председателя")

        print(f"Готово. Пароль у тестовых аккаунтов: {TEST_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
