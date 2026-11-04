# CLAUDE.md

Навигационная карта проекта **ИК — Таск-трекер** (креативное агентство «Информационный комитет»). Не пересказ кода — а где что искать.

## Стек

- **Backend:** FastAPI + SQLAlchemy 2 + SQLite + Alembic. JWT-авторизация (pyjwt), хеш паролей bcrypt. Pydantic-settings для конфига. Тесты — pytest + httpx TestClient.
- **Frontend:** Vue 3 (`<script setup>`) + Vite + Pinia + Vue Router + Axios.

## Запуск

**Локально (Linux) — через docker compose**, `docker-compose.dev.yml`: код примонтирован, бэк с `--reload`, фронт — Vite с HMR (прокси `/api` → бэк через `VITE_PROXY_TARGET`). Фронт: **http://localhost:5180** (5173 занят другим проектом), API: `127.0.0.1:8100`. База — том `ik-tracker-dev_backend_data`.

```
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml run --rm backend pytest          # тесты (~3 мин)
docker compose -f docker-compose.dev.yml exec backend python -m scripts.seed_demo_tasks
docker compose -f docker-compose.dev.yml --profile bot up -d              # + бот, нужен bot/.env с ТЕСТОВЫМ токеном
```

**Тестовые роли:** `scripts.seed_test_roles` (после демо-сидов) создаёт `t.chairman`, `t.secretary`, `t.head` (рук. НВК), `t.activist`, `t.editorial` с паролем `test12345` и данными под них. В dev-сборке справа внизу плашка `dev` — `DevRoleSwitcher` (вход под ролью в один клик); в прод-бандл не попадает (`import.meta.env.DEV` в `App.vue`). Списки аккаунтов в сиде и в компоненте держать в согласии.

Бот (бывший flood, aiogram 3 + SQLite) — в `bot/`, на сервере пока живёт отдельно в `/root/flood` (контейнер `flood-bot-1`). Боевой токен локально не использовать: второй polling выбьет прод-бота. `bot/database/bot.db.bak_*_server` — бэкап боевой базы, в git не идёт (там персданные актива, как и в `*.xlsx`).

На Windows — **`start.bat`** в корне. Проще всего — **`start.bat`** в корне (поднимает бэк и фронт в двух окнах + открывает браузер). Прод на сервере — `docker compose up -d --build`, адрес **https://rezonans26.ru** (общий edge-прокси `/root/infra/nginx.conf` → контейнер `ik-tracker-frontend` в сети `arkadium_shared`; запасной вход — `:8084`). nginx фронта проксирует `/api` на `ik-tracker-backend` — по имени контейнера, не `backend`: в общей сети есть чужой `backend`. Бэк наружу — только `127.0.0.1:8100` для отладки; детали в README. Вручную:

```
# Backend (из backend/)
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8100
# Frontend (из frontend/)
npm run dev
```

- API: `http://localhost:8100/api`, Swagger: `http://localhost:8100/docs`. Фронт: `http://localhost:5173`. (Бэк на 8100, а не 8000 — 8000 занят другим сервисом на сервере.)
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

Домены: **users, auth, directions, tasks, events, leadership_notes, leadership_tasks, editorial_posts, zavod, push, personal_todos, games, broadcasts, checklists, surveys** — у каждого свой набор route/service/repository/schema/model.

Прочее: `alembic/versions/` — миграции (нумерованные `0001…`, revision id выставлен вручную). `scripts/` — `create_admin.py`, `seed_demo_tasks.py` (пароль демо `demo12345`), `seed_demo_events.py`. `tests/` — `conftest.py` даёт фикстуры `admin/manager/employee_credentials`, `client`, `direction`.

## Frontend — структура

| Папка | Назначение |
|---|---|
| `src/api/` | Axios-клиенты по доменам. `client.js` — инстанс с интерсепторами (Bearer-токен, 401 → logout). `tokenStorage.js` — токен в localStorage |
| `src/stores/` | Pinia-сторы: `auth` (юзер, токен, геттеры `isAdmin`/`isManagerOrAdmin`), `tasks` (задачи + направления), `events` |
| `src/views/` | Страницы: `LoginView`, `HomeView` (главная `/`: ближайшие мероприятия, мои задачи, «ждут проверки», «Мой день», анкеты без ответа), `TasksView` (доска, `/tasks`; старые `/?task=…`/`?private=1` роутер перекидывает сюда), `MyDayView` (личный список на день), `CalendarView`, `LeadershipTimelineView`, `EditorialView` / `EditorialPostView`, `ZavodView`, `UsersAdminView`, `GamesView` / `DurakView` / `SeaBattleView` |
| `src/components/` | `AppSidebar` (навигация + видимость пунктов по роли), `AppTabBar` (мобильный бар: Главная · Мой день · Задачи · Редакция · Ещё, календарь — в «Ещё»), `TaskCard`, `CreateTaskModal`, `EventModal` |
| `src/router/` | Маршруты + гард: `meta.requiresAuth` / `requiresAdmin` / `requiresManager` |
| `src/constants/` | `roleLabels.js`, `taskMeta.js` (статусы/приоритеты/цвета) |
| `src/utils/` | `avatar`, `formatDate`, `formatDateTime`, `calendarGrid` |
| `src/style.css` | Глобальные стили + CSS-переменные: цвета (`--bg`, `--surface`, `--accent`…), отступы `--space-*`, радиусы `--radius-*`, высота контролов `--control-h`. Здесь же общий каркас страницы: `.app-layout`, `.app-main`, `.breadcrumb`, `h1`, `.subtitle`, `.create-btn` — во вью их не дублировать |
| `src/fonts.js` | Шрифты из пакетов `@fontsource` (Golos Text, Unbounded, JetBrains Mono), лежат в сборке |

Точка входа `main.js` восстанавливает сессию (`restoreSession`) **до** монтирования.

## Соглашения

- **Роли:** `admin` / `manager` / `employee`. UI-подписи в `roleLabels.js` (manager = «Руководитель», employee = «Активист»). Бэк гейтит через `require_role`, фронт — через гард-меты и геттеры стора.
- **Видимость по ролям:** задачи фильтруются на бэке (`task_repository._visible_to` — и для списка, и для открытия по id: активист не видит ТЗ, выданные руководителям, даже по номеру).
- **ТЗ: выдача и правка** (`task_service.can_issue_to` / `can_manage`): руководитель выдаёт ТЗ только в направления, которыми руководит (`direction_heads`), админы и держатели должности — в любое. Править и удалять (`DELETE /tasks/{id}`) могут выдавший, руководитель направления, админы и должности; исполнитель — только статус. Права приходят в ответе (`can_manage`, `can_comment`), фронт их не пересчитывает. Форма выдачи и правки одна — `CreateTaskModal` (с `task` — режим правки).
- **Обсуждение ТЗ:** `task_comments`, API `/tasks/{id}/comments`, ответы — один уровень (`parent_id`). Пишут участники (выдавший, исполнители) и те, кто управляет задачей; остальные видящие — читают. Уведомление уходит участникам. На фронте — общий `CommentThread` в `TaskSheet`. Разделы «Руководству» (`/leadership-notes`) и «Таймлайн» — только admin/manager. «Руководители направлений» (`PUT /directions/{id}/heads`) — только admin.
- **Направления ↔ руководители:** связь many-to-many (`direction_heads`). Назначение сотрудника руководителем авто-повышает его роль до `manager`.
- **Актив и направление участника:** `users.is_activist` («в активе») и направления, где человек состоит — many-to-many `direction_members` (`User.directions`, в API `direction_ids`; не путать с руководством). Ставятся сами при одобрении анкеты мини-аппа и импорте из бота (из бота — все упомянутые: «дизайн, цт» → два), дальше правит админ в «Пользователях». В анкете направление одно — `user_service.set_directions` держит его в числе выбранных (анкету читают бот и заявки). В списке — фильтры по активу и направлению.
- **Ошибки:** сервис кидает доменное исключение из `services/exceptions.py`, роут ловит и отдаёт нужный HTTP-код.
- **Язык:** UI-тексты, сообщения об ошибках и комментарии — на русском.
- **Личные поручения:** задача с `is_private` без направления. Выдаёт руководство (админ или должность). Исполнителей может быть несколько — таблица `task_assignees`, у каждого свой статус; `tasks.assignee_id` — первый из них, `tasks.status` — сводный (`task_service.overall_status`). В ответе API исполнитель видит в `status` свою часть, остальные — сводный (`task_service.view`), список — в `assignees`. Видят автор, исполнители, все админы и секретарь (`task_service.sees_all_private`), остальным — 404. Правит автор (и состав через `assignee_ids`; его смена статуса двигает всех), исполнитель — только свой статус; админы и секретарь лишь смотрят. Автор может напомнить (`POST /tasks/{id}/remind`) тем, кто ещё не сдал, — не чаще раза в 30 мин (`tasks.reminded_at`); когда исполнитель сдаёт на проверку или закрывает, автору приходит уведомление. Ссылки в уведомлениях — `/tasks?task=<id>`, `TasksView` сразу открывает карточку. На фронте — раздел «Поручения» (`/tasks?private=1`), в «Все ТЗ» не попадают.
- **Telegram:** бот + мини-апп на том же фронте. Вход в мини-апп — по подписи `initData` (`core/telegram.py`, `POST /auth/telegram`), логина и пароля в мини-аппе нет (гард ведёт на `/join`, `JoinView`). Не привязанный Telegram → 404 → анкета (`registration_service.register`: ФИО, ДР, направление, группа, телефон, почта, размер, два фото в `profile_photos_dir`) → аккаунт `registration_status=pending`, `is_active=False` → админ принимает/отклоняет в «Пользователях» (`RegistrationsPanel`, `/users/registrations`); анкета с фото уходит альбомом в `TELEGRAM_ANKETA_CHAT_ID`. При одобрении анкета дописывается в базу бота (`bot_sync_service`: `activists`/`activist_links`/`activist_photos`, существующий человек ищется по Telegram id, потом по тегу), чтобы его находил `!инфо`; база бота подключена к бэкенду томом (`BOT_DATA_DIR` → `/bot-data`, `BOT_DB_PATH`). Фото для бота — `file_id` из ответа на альбом в архив (`user_profiles.photo{1,2}_file_id`). Уже заведённые аккаунты привязывают Telegram из браузера: «Подключить Telegram» → одноразовый код → `t.me/<бот>?startapp=link_<код>` → `/join?link=` → `POST /auth/telegram/claim`. Параметр запуска (`start_param`) разбирает `main.js` и после установки роутера делает `router.replace` — сам роутер запоминает адрес ещё при создании. Уведомления: `push_service.send_to_users` шлёт и web push, и сообщение бота (`telegram_service`). **Бот → трекер** (`bot_import_service`): активные анкеты из базы бота заводятся одобренными аккаунтами трекера (логин `tg<id>`/`bot<id анкеты>`, без пароля), человек ищется по Telegram id, потом по тегу — дублей нет; при старте бэкенда и раз в `BOT_IMPORT_INTERVAL_MINUTES` (10), вручную — «Подтянуть из бота» в «Пользователях». Вход из мини-аппа без привязки: сначала аккаунт с тем же тегом без Telegram id (тег подтверждён подписью) — привязываем, потом анкета в боте — заводим на лету (`auth_service._match_existing`); анкета в мини-аппе — только если человека нет нигде. Бот общий с flood (`@IK_FLOOD_BOT`, код в `bot/`): токен тот же, getUpdates слушает только flood, а бэкенд по токену лишь шлёт сообщения и проверяет `initData`. Вход в трекер со стороны бота — `bot/handlers/command_tracker.py` (кнопка меню, `!трекер`, `/start web|tracker`). Старый `backend/app/bot.py` в compose не запускается — с общим токеном он выбил бы flood. Без `TELEGRAM_BOT_TOKEN` всё это молча выключено. Фронт: `utils/telegram.js` (скрипт telegram.org грузится только при запуске из Telegram).
- **Игры (дурак):** раздел «Игры» виден всем. Механика — `app/games/durak.py` (чистая логика, перенесена из бота flood; место 1 — человек или бот), состояние партии — JSON в `durak_games.state`, `version` растёт с каждым ходом (ход по старой версии → 409). Партию видят только её игроки; чужая видна лишь пока ждёт соперника (`can_join`), иначе 404. Лобби, в которое никто не вошёл, живёт 5 минут (`LOBBY_TTL_MINUTES`; срок проверяется лениво в `_expire`), потом `cancelled` — из «Моих партий» пропадает, по ссылке не войти. Фронт опрашивает стол раз в 1.5 с, пока ход у соперника. После входа второго — `ready_check` без таймера: место занято, оба жмут «Готов» сколько нужно; до старта гость может выйти (место снова свободно, окно ожидания начинается заново), а создатель — закрыть лобби. Приглашение в чат актива (`TELEGRAM_GAMES_CHAT_ID`) бэкенд шлёт сам `sendPhoto` с превью `public/og/durak-invite.png` и правит подпись/кнопку по ходу партии (`_sync_chat`). Ссылка «Присоединиться» — `t.me/<бот>?startapp=durak_<код>` (если у бота в BotFather включён основной мини-апп; фронт ловит `start_param` в `main.js`), иначе `?start=durak_<код>` — тогда flood отвечает кнопкой мини-аппа.
- **Морской бой:** устроен как дурак — `app/games/seabattle.py` (классика 10×10, флот 4-3-3-2-2-2-1-1-1-1, без касаний; бот без памяти — цели выводит из выстрелов), `sea_battle_service`, таблица `sea_battle_games`, API `/games/sea`. Лобби то же (ожидание → `ready_check` 5 с), дальше `placing` (каждый расставляет флот, версию для `place` не сверяем — расстановки независимы) → `playing`. Чужой флот в ответе не отдаётся — только выстрелы и потопленные корабли (в конце — весь). Фронт: `SeaBattleView`, поле — `components/SeaGrid.vue`, расстановка — `utils/seabattle.js`. Превью для чата — `public/og/sea-invite.png`, `start_param` — `sea_<код>`.
- **Бункер:** партия на 4–16 человек, обсуждают вживую — приложение ведёт карты, фазы и голосование. Механика — `app/games/bunker.py` (состояние — словарь в JSON), колоды — `app/games/bunker_cards.py`, `bunker_service`, таблицы `bunker_games` + `bunker_players` (лобби), API `/games/bunker` (`join`/`leave`/`start`/`invite-chat`/`move`). Лобби без проверки «Готов»: создатель жмёт «Начать». Раунд: `reveal` (каждый открывает одну карту) → `discuss` → `vote` (если по `schedule()` в раунде есть изгнание) → `result`; ничья — переголосование среди лидеров, повторная — жребий. Ведёт создатель (`advance`, версию сверяем только для `advance`/`stop`). После старта место игрока — индекс в `state["user_ids"]`. Закрытые карты отдаются только владельцу. Цвета характеристик — цвета направлений. Превью — `public/og/bunker-invite.png`, `start_param` — `bunker_<код>`. **Столы для очной игры** заводит админ на `/games/tables` (можно пустыми и пачкой — «Создать столы», ребята садятся сами из «Открытых столов») (`BunkerTablesView`, API `/games/bunker/tables`): название, ведущий и игроки по Telegram-тегам (`user_repository.find_by_telegram_tags`, ненайденные теги возвращаются в `missing`). Стол = партия с `title`; пока карты не розданы, к нему можно сесть самому — по ссылке или из «Открытых столов» в «Играх» (`GET /games/bunker/open-tables`), и выйти. Состав админ меняет только до раздачи; правка не выкидывает севших без Telegram-тега (их не перечислить тегами). Ведущий не из списка игроков — наблюдатель (`observer`): видит все карты, ведёт фазы, сам не открывает и не голосует. Посаженным приходит уведомление со ссылкой на стол.
- **Игры из бота:** `!дурак` во flood больше не играет сам, а открывает дурака в трекере (`/games/durak/new?vs=bot|human` создаёт партию и открывает её). В группе web_app-кнопки нельзя — там ссылки `t.me/<бот>?start=play_durak_bot|human` (или `startapp=`, если включён основной мини-апп). Разбор пейлоадов — `bot/handlers/command_tracker.py`, на фронте — `START_ROUTES` в `main.js`. Старый `!морскойбой` в боте не трогали.
- **Рассылка** (`/broadcast`, только админ): сообщение от бота в личку всем, кого он знает — Telegram id из трекера и из базы бота (`bot_sync_service.known_telegram_ids`: `activist_links` + `stats_users`). Текст с разметкой `**жирный**` / `__курсив__` (`broadcast_service.render_text`, превью на фронте повторяет её), кнопки — ссылка (`url`) или раздел трекера мини-аппом (`path`). «Отправить себе» — синхронно; общая рассылка — в фоновом потоке ~20 сообщений/с, прогресс в `broadcasts` (фронт опрашивает), одновременно одна (зависшая дольше 20 мин не держит очередь). 403 от Telegram (не запускал бота) — «не дошло».
- **Чек-листы «Найди того, кто…»** (`/checklists`, только админ): факты (по умолчанию — `app/activities/checklist_facts.py`, творительный падеж под «Сфоткайся с») раздаются по три всем, кого знает бот (`checklist_service.deal`: круги перемешанных фактов — каждый почти поровну, в листе без повторов). Картинку листа рисует админка на canvas (`utils/checklistImage.js`, элементы макета Штаб'26-27 в `public/checklist/`) и загружает JPEG; бэкенд рассылает `sendPhoto` в фоне, перед отправкой пишет строку в таблицу `checklists` базы бота. Фото в ответ принимает бот flood (`bot/handlers/command_checklist.py`, роутер сразу после анкеты): без подписи — к первому пустому пункту, с подписью «1/2/3» — замена; пересылает в группу `CHECKLIST_CHAT_ID` (env бота) с ФИО и пунктом, file_id — в ту же строку. Админка показывает прогресс и сами фото (`getFile` через бэкенд). «Отправить по юзернейму» (`/checklists/by-tag` → `/cards/{id}/send`): не дошедший лист — заново, человеку не из раздачи — новый свободный из самых редких фактов; повторная отправка того же листа присланные фото не стирает. Найти человека по тегу помогает `bot_contacts` — бот записывает всех, кто пишет ему в личку (`bot/middlewares/dm_contacts.py`), они же попадают в рассылку.
- **Анкеты** (`/surveys`): админ собирает опрос (`SurveyManageView`: вопросы — короткий/развёрнутый ответ, один/несколько вариантов, шкала 1…N; «Отправить» — выбор людей с быстрыми кнопками «Весь актив» / по направлению; «Ответы» — сводка по вопросам, по людям, напоминание не ответившим раз в 30 мин, закрыть приём, CSV), получатели отвечают на `/surveys/<id>` (`SurveyFillView`; ссылка приходит уведомлением бота + web push, без Telegram — только в разделе «Анкеты»). Таблицы `surveys` (вопросы — JSON, ответы хранятся по `id` вопроса), `survey_recipients`, `survey_responses` (один ответ на человека, переотправляется, пока анкета открыта). Вопросы правятся, пока нет ни одного ответа. Не получатель видит анкету как 404; админ — предпросмотр. Каскад при удалении — вручную (`PRAGMA foreign_keys` выключен).
- **Календарь:** время мероприятий — «как на часах», без пояса (`schemas/event._wall_clock` отбрасывает пояс, фронт шлёт `YYYY-MM-DDTHH:MM:00`, не `toISOString()`): SQLite пояс не хранит, и UTC с «Z» уезжал назад на каждом сохранении. «Приду / Не приду» — `event_rsvps` (`PUT /events/{id}/rsvp`, null снимает ответ), отвечает любой; в `EventOut` — `my_rsvp`, счётчики `going_count` / `not_going_count` всем, а списки имён `going` / `not_going` — только админам (остальным пустые, `event_service.with_rsvps`).
- **«Мой день»:** личный список (`/personal-todos`) виден только владельцу — чужой пункт отдаётся как 404, ролей и руководства это не касается.
- **Дизайн:** размеры текста только 11/12/13/14/15/18/20/24px, радиусы 6/8/12/18px, отступы из `--space-*`. Цвета — только из переменных. Заголовки в обычном регистре, капс — только `.breadcrumb` и подписи секций меню. Иконки — `BaseIcon`, эмодзи в интерфейсе не используем. Брендбук: https://claude.ai/artifact/6K7Uv69eWpVDQb3qbNFCSi
- **Стиль:** новый код повторяет соседний (вёрстка вью, нейминг репозиториев/сервисов, формат миграций).
