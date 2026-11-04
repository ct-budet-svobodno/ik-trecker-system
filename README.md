# ИК — Таск-трекер

Таск-трекер для креативного агентства «Информационный комитет».

Шаг 1 (готово): авторизация по логину/паролю, роли `admin` / `manager` / `employee`, управление пользователями.
Дальше: контент задач и ролевая видимость, Telegram-бот для напоминаний, PWA.

## Стек

- Backend: FastAPI + SQLAlchemy + SQLite + Alembic
- Frontend: Vue 3 + Vite + Pinia + Vue Router + Axios

## Запуск в Docker (на сервере)

```bash
git clone https://github.com/ct-budet-svobodno/ik-trecker-system.git
cd ik-trecker-system
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

### Автодеплой через GitHub Actions

Репозиторий приватный, поэтому серверу нужен read-only доступ к нему. Пуш в `main` запускает `.github/workflows/deploy.yml`: workflow заходит на сервер по SSH, обновляет код из этого репозитория и пересобирает контейнеры. Секреты приложения (`.env`, база, токены Telegram) остаются на сервере и в GitHub не передаются.

**1. Доступ сервера к репозиторию (один раз).** В организации `ct-budet-svobodno` deploy keys запрещены, поэтому используем fine-grained PAT только на чтение:

1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Resource owner — `ct-budet-svobodno`, доступ только к репозиторию `ik-trecker-system`.
3. Repository permissions → **Contents: Read-only**. Больше прав не выдавать.
4. Скопировать токен.

На сервере в папке проекта:

```bash
cd /путь/к/ik-trecker-system
git remote set-url origin https://github.com/ct-budet-svobodno/ik-trecker-system.git
git config credential.helper store
git fetch origin main
# username: x-access-token
# password: <fine-grained PAT>
git checkout main
git pull --ff-only origin main
```

Токен сохранится в `~/.git-credentials` на сервере и в репозиторий не попадёт.

Если сделать репозиторий публичным, PAT не нужен — достаточно HTTPS-адреса без авторизации.

**2. Доступ GitHub Actions к серверу.** В GitHub → Settings → Secrets and variables → Actions добавьте:

| Секрет | Значение |
| --- | --- |
| `DEPLOY_HOST` | хост или IP сервера |
| `DEPLOY_USER` | пользователь SSH |
| `DEPLOY_PATH` | абсолютный путь к проекту на сервере |
| `DEPLOY_SSH_KEY` | приватный SSH-ключ для деплоя |
| `DEPLOY_PORT` | порт SSH (необязательно, по умолчанию 22) |

Публичную часть `DEPLOY_SSH_KEY` добавьте в `~/.ssh/authorized_keys` пользователя `DEPLOY_USER` на сервере. Пока `DEPLOY_HOST` не задан, workflow завершается без деплоя. После настройки секретов деплой запускается пушем в `main` или вручную через вкладку Actions.

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
