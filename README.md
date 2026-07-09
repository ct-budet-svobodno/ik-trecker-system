# ИК — Таск-трекер

Таск-трекер для креативного агентства «Информационный комитет».

Шаг 1 (готово): авторизация по логину/паролю, роли `admin` / `manager` / `employee`, управление пользователями.
Дальше: контент задач и ролевая видимость, Telegram-бот для напоминаний, PWA.

## Стек

- Backend: FastAPI + SQLAlchemy + SQLite + Alembic
- Frontend: Vue 3 + Vite + Pinia + Vue Router + Axios

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
uvicorn app.main:app --reload --port 8000
```

API будет на `http://localhost:8000/api`, документация — на `http://localhost:8000/docs`.

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
