from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./ik_tracker.db"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 43200
    cors_origins: str = "http://localhost:5173"

    # Web Push (VAPID). Пустые ключи = пуши выключены (например, в тестах).
    # Генерация: python -m scripts.generate_vapid_keys
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:iccommittee25@gmail.com"

    # Telegram: бот для уведомлений и мини-аппа. Пустой токен = Telegram выключен
    # (вход через мини-апп и сообщения бота не работают, веб — как обычно).
    telegram_bot_token: str = ""
    # Адрес, который бот открывает как мини-апп (и куда ведут кнопки в сообщениях).
    webapp_url: str = "https://rezonans26.ru"
    # Сколько секунд initData из Telegram считается свежей.
    telegram_auth_max_age: int = 86400
    # Групповой чат актива, куда бот публикует приглашения в игры (бот должен
    # там состоять). Пусто — кнопки «Позвать в чат» нет, только личная ссылка.
    telegram_games_chat_id: int | None = None
    # Группа-архив, куда уходят анкеты новых участников с фото (бот должен там
    # состоять). Пусто — анкеты только в трекере.
    telegram_anketa_chat_id: int | None = None
    # Куда складывать фото из анкет (в проде — внутри тома с базой).
    profile_photos_dir: str = "data/profile_photos"
    # Картинки чек-листов «Найди того, кто…» (рисует админка, рассылает бот).
    checklist_images_dir: str = "data/checklists"
    # Как часто подтягивать анкеты из базы бота в трекер (0 — только вручную).
    bot_import_interval_minutes: int = 10
    # База бота flood (SQLite): одобренная анкета из мини-аппа дописывается туда,
    # чтобы человека находил !инфо. Пусто или файла нет — синхронизация выключена.
    bot_db_path: str | None = None

    @field_validator("telegram_games_chat_id", "telegram_anketa_chat_id", "bot_db_path", mode="before")
    @classmethod
    def _empty_chat_id_is_none(cls, value):
        # docker compose передаёт незаданную переменную пустой строкой.
        return None if value == "" else value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
