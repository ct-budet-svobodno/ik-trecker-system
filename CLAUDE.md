# CLAUDE.md

Навигационная карта проекта **ИК — Таск-трекер** (креативное агентство «Информационный комитет»). Не пересказ кода — а где что искать.

## Стек

- **Backend:** FastAPI + SQLAlchemy 2 + SQLite + Alembic. JWT-авторизация (pyjwt), хеш паролей bcrypt. Pydantic-settings для конфига. Тесты — pytest + httpx TestClient.
- **Frontend:** Vue 3 (`<script setup>`) + Vite + Pinia + Vue Router + Axios.

## Запуск

Проще всего — **`start.bat`** в корне (поднимает бэк и фронт в двух окнах + открывает браузер). Вручную:

```
# Backend (из backend/)
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Frontend (из frontend/)
npm run dev
```

- API: `http://localhost:8000/api`, Swagger: `http://localhost:8000/docs`. Фронт: `http://localhost:5173`.
- Логины (dev): `admin / admin123`; демо-юзеры (`i.manaev` и др.) — `demo12345`.
- **Готчи:** Node.js ставится отдельно (winget `OpenJS.NodeJS.LTS`). Vite слушает `localhost` (не `127.0.0.1`). Проект в OneDrive — Vite стартует медленно (~40с).

## Тесты и миграции

```
# Тесты (из backend/, in-memory SQLite, БД не трогают)
venv\Scripts\python.exe -m pytest
# Миграции
venv\Scripts\python.exe -m alembic upgrade head
venv\Scripts\python.exe -m alembic revision --autogenerate -m "..."
```

## Backend — слоистая архитектура

Поток запроса: **route → service → repository → model**, на входе/выходе — **schema** (Pydantic).

| Слой | Папка | Назначение |
|---|---|---|
| Роуты | `app/api/routes/` | HTTP-эндпоинты, проверка прав, маппинг ошибок в HTTP. Регистрация — в `routes/__init__.py` |
| Зависимости | `app/api/deps.py` | `get_current_user`, `require_role(*roles)` (гейт по ролям) |
| Сервисы | `app/services/` | Бизнес-логика. Доменные ошибки — в `services/exceptions.py` |
| Репозитории | `app/repositories/` | Доступ к БД (SQLAlchemy-запросы), без бизнес-логики |
| Модели | `app/models/` | ORM-таблицы. Реэкспорт — `models/__init__.py` |
| Схемы | `app/schemas/` | Pydantic-валидация запросов/ответов (`*Create`, `*Update`, `*Out`) |
| Ядро | `app/core/` | `config.py` (env-настройки, `.env`), `security.py` (JWT, bcrypt) |
| БД | `app/db/` | `base.py` (Base), `session.py` (`get_db`, SessionLocal) |
| Точка входа | `app/main.py` | Сборка приложения, CORS, подключение `api_router` (префикс `/api`) |

Домены: **users, auth, directions, tasks, events, leadership_notes** — у каждого свой набор route/service/repository/schema/model.

Прочее: `alembic/versions/` — миграции (нумерованные `0001…`, revision id выставлен вручную). `scripts/` — `create_admin.py`, `seed_demo_tasks.py` (пароль демо `demo12345`), `seed_demo_events.py`. `tests/` — `conftest.py` даёт фикстуры `admin/manager/employee_credentials`, `client`, `direction`.

## Frontend — структура

| Папка | Назначение |
|---|---|
| `src/api/` | Axios-клиенты по доменам. `client.js` — инстанс с интерсепторами (Bearer-токен, 401 → logout). `tokenStorage.js` — токен в localStorage |
| `src/stores/` | Pinia-сторы: `auth` (юзер, токен, геттеры `isAdmin`/`isManagerOrAdmin`), `tasks` (задачи + направления), `events` |
| `src/views/` | Страницы: `LoginView`, `TasksView` (доска), `CalendarView`, `TimelineView`, `LeadershipView`, `DirectionsAdminView` |
| `src/components/` | `AppSidebar` (навигация + видимость пунктов по роли), `TaskCard`, `CreateTaskModal`, `EventModal` |
| `src/router/` | Маршруты + гард: `meta.requiresAuth` / `requiresAdmin` / `requiresManager` |
| `src/constants/` | `roleLabels.js`, `taskMeta.js` (статусы/приоритеты/цвета) |
| `src/utils/` | `avatar`, `formatDate`, `formatDateTime`, `calendarGrid` |
| `src/style.css` | Глобальные стили + CSS-переменные тёмной темы (`--bg`, `--surface`, `--accent`…) |

Точка входа `main.js` восстанавливает сессию (`restoreSession`) **до** монтирования.

## Соглашения

- **Роли:** `admin` / `manager` / `employee`. UI-подписи в `roleLabels.js` (manager = «Руководитель»). Бэк гейтит через `require_role`, фронт — через гард-меты и геттеры стора.
- **Видимость по ролям:** задачи фильтруются на бэке (`task_repository.list_visible_for`). Разделы «Руководству» (`/leadership-notes`) и «Таймлайн» — только admin/manager. «Руководители направлений» (`PUT /directions/{id}/heads`) — только admin.
- **Направления ↔ руководители:** связь many-to-many (`direction_heads`). Назначение сотрудника руководителем авто-повышает его роль до `manager`.
- **Ошибки:** сервис кидает доменное исключение из `services/exceptions.py`, роут ловит и отдаёт нужный HTTP-код.
- **Язык:** UI-тексты, сообщения об ошибках и комментарии — на русском.
- **Стиль:** новый код повторяет соседний (вёрстка вью, нейминг репозиториев/сервисов, формат миграций).
