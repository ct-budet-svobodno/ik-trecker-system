"""Создаёт первого админа. Запускать один раз после `alembic upgrade head`:

    python -m scripts.create_admin
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from app.db.session import SessionLocal
from app.models.user import UserRole
from app.repositories import user_repository
from app.schemas.user import UserCreate
from app.services import user_service
from app.services.exceptions import UsernameTakenError


def main() -> None:
    parser = argparse.ArgumentParser(description="Создать первого администратора")
    parser.add_argument("--username", help="Логин администратора")
    parser.add_argument("--full-name", help="Полное имя")
    args = parser.parse_args()

    username = args.username or input("Логин: ").strip()
    full_name = args.full_name or input("Полное имя: ").strip()
    password = getpass.getpass("Пароль: ")
    password_confirm = getpass.getpass("Повторите пароль: ")

    if password != password_confirm:
        print("Пароли не совпадают.")
        sys.exit(1)

    db = SessionLocal()
    try:
        if user_repository.get_by_username(db, username) is not None:
            print(f"Пользователь с логином '{username}' уже существует — ничего не делаю.")
            return
        try:
            user_create = UserCreate(
                username=username,
                password=password,
                full_name=full_name,
                role=UserRole.ADMIN,
            )
        except ValidationError as exc:
            print(f"Некорректные данные: {exc}")
            sys.exit(1)
        try:
            user = user_service.create_user(db, user_create)
        except UsernameTakenError as exc:
            print(str(exc))
            sys.exit(1)
        print(f"Админ '{user.username}' создан (id={user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
