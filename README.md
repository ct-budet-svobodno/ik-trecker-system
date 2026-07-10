# ИК — Таск-трекер

Таск-трекер для креативного агентства «Информационный комитет».

Шаг 1 (готово): авторизация по логину/паролю, роли `admin` / `manager` / `employee`, управление пользователями.
Дальше: контент задач и ролевая видимость, Telegram-бот для напоминаний, PWA.

## Стек

- Backend: FastAPI + SQLAlchemy + SQLite + Alembic
- Frontend: Vue 3 + Vite + Pinia + Vue Router + Axios

## Запуск в Docker (на сервере)

```bash
git clone https://github.com/AnatolyKozmin/task-trecker-ik.git
cd task-trecker-ik
cp .env.example .env        # задайте JWT_SECRET_KEY (например: openssl rand -hex 32)
docker compose up -d --build
```

После старта:

- Сайт: `http://<ip-сервера>:8084`
- API/Swagger (только с самого сервера): `http://127.0.0.1:8100/docs`

Миграции применяются автоматически при старте бэкенда. Первого админа создать один раз:

```bash
docker compose exec backend python -m scripts.create_admin
```

База (SQLite) хранится в docker-томе `backend_data` и переживает пересборку. Порты 8084/8100 выбраны свободными от других проектов на сервере; поменять можно в `docker-compose.yml`.

Обновление после новых коммитов:

```bash
git pull && docker compose up -d --build
```

## Запуск (Windows)

### 1. Backend

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Откройте `backend/.env` и замените `JWT_SECRET_KEY` на свою случайную строку.

Накатить миграции и создать первого админа:

```
alembic upgrade head
python -m scripts.create_admin
```

Запустить сервер:

```
uvicorn app.main:app --reload --port 8100
```

API будет на `http://localhost:8100/api`, документация — на `http://localhost:8100/docs`.

### 2. Frontend

```
cd frontend
npm install
copy .env.example .env
npm run dev
```

Откройте `http://localhost:5173` и войдите под аккаунтом, который создали скриптом `create_admin`.

Дальше всех остальных сотрудников и руководителей заводит админ через раздел пользователей (`POST /api/users`).

## Тесты backend

```
cd backend
venv\Scripts\activate
pytest
```

## Изменение схемы БД

После любого изменения моделей в `backend/app/models/`:

```
alembic revision --autogenerate -m "описание изменения"
alembic upgrade head
```
