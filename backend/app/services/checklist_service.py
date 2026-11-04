"""Чек-листы «Найди того, кто…»: у каждого три факта, нужно найти подходящих
людей и сфоткаться с ними. Только админ.

1. prepare — факты перемешиваются и раздаются по три всем, кого знает бот
   (как у рассылки: трекер + база бота). Каждый факт достаётся почти поровну
   людей (разница — не больше одного), внутри листа факты не повторяются.
2. Картинки рисует админка (canvas по макету Штаб'26-27) и загружает: save_image.
3. send — в фоне каждому sendPhoto с его листом. Перед отправкой строка
   пишется в базу бота (таблица checklists): по ней бот flood принимает
   ответные фото и пересылает их в группу с ФИО и номером пункта
   (bot/handlers/command_checklist.py).
4. progress — сколько фото прислал каждый (читаем из базы бота).
"""
import datetime
import json
import logging
import random
import sqlite3
import threading
import time
import urllib.error
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.activities.checklist_facts import DEFAULT_FACTS
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.checklist import ChecklistCard, ChecklistStatus
from app.models.user import User
from app.services import bot_sync_service, telegram_service
from app.services.exceptions import ChecklistError

logger = logging.getLogger(__name__)

FACTS_PER_CARD = 3
SEND_INTERVAL = 0.1
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Та же схема создаётся ботом (bot/database/checklist_models.py) — кто первый.
BOT_TABLE = """
CREATE TABLE IF NOT EXISTS checklists (
    tg_id BIGINT PRIMARY KEY,
    number INTEGER NOT NULL,
    full_name VARCHAR NOT NULL,
    username VARCHAR,
    facts TEXT NOT NULL,
    photo1 VARCHAR,
    photo2 VARCHAR,
    photo3 VARCHAR,
    sent_at DATETIME,
    updated_at DATETIME
)
"""

_send_lock = threading.Lock()
_sending = False


# ── Раздача фактов ──

def deal(facts: list[str], people: int, rng: random.Random | None = None) -> list[list[str]]:
    """people листов по три разных факта; факты расходуются по кругу, каждый круг
    перемешан заново — поэтому каждый факт выпадает почти одинаковое число раз."""
    facts = list(dict.fromkeys(f.strip() for f in facts if f.strip()))
    if len(facts) < FACTS_PER_CARD:
        raise ChecklistError(f"Нужно хотя бы {FACTS_PER_CARD} факта")
    rng = rng or random.Random()
    pool: list[str] = []
    while len(pool) < people * FACTS_PER_CARD:
        cycle = facts[:]
        rng.shuffle(cycle)
        pool.extend(cycle)
    cards = [pool[i * FACTS_PER_CARD:(i + 1) * FACTS_PER_CARD] for i in range(people)]
    # На стыке кругов в лист может попасть один факт дважды — меняем с соседним листом.
    for i, card in enumerate(cards):
        for j in range(FACTS_PER_CARD):
            if card.count(card[j]) == 1:
                continue
            for other in cards[:i] + cards[i + 1:]:
                k = next(
                    (k for k, f in enumerate(other) if f not in card and card[j] not in other), None
                )
                if k is not None:
                    card[j], other[k] = other[k], card[j]
                    break
    return cards


def _people(db: Session) -> dict[int, dict]:
    """tg_id → имя и тег: из базы бота, имена из трекера — главнее."""
    people = bot_sync_service.known_people()
    users = db.scalars(select(User).where(User.telegram_id.is_not(None), User.is_active.is_(True)))
    for user in users:
        person = people.setdefault(user.telegram_id, {"name": None, "username": None})
        person["name"] = user.full_name
        person["username"] = (user.telegram_username or person["username"] or "").lstrip("@") or None
    for person in people.values():
        if not person["name"]:
            person["name"] = f"@{person['username']}" if person["username"] else "Без имени"
    return people


def people_count(db: Session) -> int:
    return len(_people(db))


def list_cards(db: Session) -> list[ChecklistCard]:
    return list(db.scalars(select(ChecklistCard).order_by(ChecklistCard.number)))


def prepare(db: Session, facts: list[str]) -> list[ChecklistCard]:
    """Раздать заново. Уже отправленные листы не трогаем — их сначала сбрасывают."""
    if db.scalar(select(ChecklistCard.id).where(ChecklistCard.status != ChecklistStatus.DRAFT)):
        raise ChecklistError("Чек-листы уже разосланы. Чтобы раздать заново, сначала начните заново")
    people = _people(db)
    if not people:
        raise ChecklistError("Некому раздавать: бот пока никого не знает")
    db.execute(delete(ChecklistCard))
    _clear_images()
    ordered = sorted(people.items(), key=lambda item: item[1]["name"].lower())
    hands = deal(facts, len(ordered))
    for number, ((tg_id, person), hand) in enumerate(zip(ordered, hands), 1):
        db.add(ChecklistCard(
            tg_id=tg_id, number=number, full_name=person["name"], username=person["username"], facts=hand,
        ))
    db.commit()
    return list_cards(db)


def _images_dir() -> Path:
    path = Path(settings.checklist_images_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _image_path(card: ChecklistCard) -> Path:
    return _images_dir() / f"{card.id}.jpg"


def _clear_images() -> None:
    for file in _images_dir().glob("*.jpg"):
        file.unlink(missing_ok=True)


def save_image(db: Session, card_id: int, data: bytes) -> ChecklistCard:
    card = db.get(ChecklistCard, card_id)
    if card is None:
        raise ChecklistError("Чек-лист не найден")
    if len(data) > MAX_IMAGE_BYTES:
        raise ChecklistError("Картинка больше 5 МБ")
    if not data.startswith(b"\xff\xd8"):
        raise ChecklistError("Нужна картинка в JPEG")
    _image_path(card).write_bytes(data)
    card.image_ready = True
    db.commit()
    return card


def image(db: Session, card_id: int) -> bytes | None:
    card = db.get(ChecklistCard, card_id)
    if card is None or not card.image_ready:
        return None
    path = _image_path(card)
    return path.read_bytes() if path.is_file() else None


# ── База бота ──

def _bot_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.bot_db_path, timeout=15)
    conn.execute(BOT_TABLE)
    return conn


def _now() -> str:
    return datetime.datetime.now(bot_sync_service.MSK).replace(tzinfo=None).isoformat(" ")


def _bot_put(card: ChecklistCard) -> None:
    conn = _bot_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO checklists (tg_id, number, full_name, username, facts, sent_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(tg_id) DO UPDATE SET number = excluded.number, "
                "full_name = excluded.full_name, username = excluded.username, facts = excluded.facts, "
                # Тот же лист прислали повторно — присланные фото не теряем.
                "photo1 = CASE WHEN checklists.facts = excluded.facts THEN checklists.photo1 END, "
                "photo2 = CASE WHEN checklists.facts = excluded.facts THEN checklists.photo2 END, "
                "photo3 = CASE WHEN checklists.facts = excluded.facts THEN checklists.photo3 END, "
                "sent_at = excluded.sent_at, updated_at = excluded.updated_at",
                (card.tg_id, card.number, card.full_name, card.username,
                 json.dumps(card.facts, ensure_ascii=False), _now(), _now()),
            )
    finally:
        conn.close()


def _bot_drop(tg_id: int | None = None) -> None:
    if not bot_sync_service.enabled():
        return
    conn = _bot_conn()
    try:
        with conn:
            if tg_id is None:
                conn.execute("DELETE FROM checklists")
            else:
                conn.execute("DELETE FROM checklists WHERE tg_id = ?", (tg_id,))
    finally:
        conn.close()


def bot_photos() -> dict[int, list[str | None]]:
    """tg_id → file_id трёх фото (None — ещё нет)."""
    if not bot_sync_service.enabled():
        return {}
    conn = _bot_conn()
    try:
        rows = conn.execute("SELECT tg_id, photo1, photo2, photo3 FROM checklists").fetchall()
    finally:
        conn.close()
    return {row[0]: list(row[1:]) for row in rows}


def photo(db: Session, card_id: int, slot: int) -> bytes | None:
    card = db.get(ChecklistCard, card_id)
    if card is None or slot not in (1, 2, 3):
        return None
    file_id = bot_photos().get(card.tg_id, [None] * 3)[slot - 1]
    if not file_id:
        return None
    try:
        return telegram_service.download_file(file_id)
    except Exception as exc:
        logger.warning("Чек-лист: не скачалось фото %s: %s", file_id, exc)
        return None


# ── Рассылка ──

def caption(card: ChecklistCard) -> str:
    esc = telegram_service.escape
    lines = [f"<b>Чек-лист №{card.number}</b>", "Найди среди актива людей под каждый пункт и сфоткайся с ними:", ""]
    lines += [f"{i}. Сфоткайся с {esc(fact)}" for i, fact in enumerate(card.facts, 1)]
    lines += [
        "",
        "Присылай фото сюда по порядку: первое — к пункту 1, второе — к пункту 2, третье — к пункту 3.",
        "Перепутал — пришли новое фото с подписью «1», «2» или «3», и оно заменит старое.",
    ]
    return "\n".join(lines)


def _deliver(db: Session, card: ChecklistCard, data: bytes) -> None:
    """Отправить один лист; сначала строка в базу бота — ответное фото может
    прийти через секунду после листа."""
    _bot_put(card)
    try:
        telegram_service.send_photo_file(card.tg_id, data, caption(card), f"checklist-{card.number}.jpg")
        card.status, card.sent_at = ChecklistStatus.SENT, datetime.datetime.now(datetime.UTC)
    except urllib.error.HTTPError as exc:
        logger.info("Чек-лист %s не доставлен (%s)", card.number, exc.code)
        card.status = ChecklistStatus.FAILED
        _bot_drop(card.tg_id)
    except Exception as exc:
        logger.warning("Чек-лист %s: %s", card.number, exc)
        card.status = ChecklistStatus.FAILED
        _bot_drop(card.tg_id)
    db.commit()


def send_test(db: Session, admin: User) -> ChecklistCard:
    """Проверка на себе: отправить только свой лист — дальше можно прислать
    боту фото и посмотреть, как они дойдут до группы."""
    _check_ready()
    card = None
    if admin.telegram_id is not None:
        card = db.scalar(select(ChecklistCard).where(ChecklistCard.tg_id == admin.telegram_id))
    if card is None:
        raise ChecklistError("Вашего листа нет: к аккаунту не привязан Telegram или вас не было в раздаче")
    data = image(db, card.id)
    if data is None:
        raise ChecklistError("Картинка вашего листа не готова — подготовьте ещё раз")
    _deliver(db, card, data)
    if card.status != ChecklistStatus.SENT:
        raise ChecklistError("Telegram не принял — откройте бота и нажмите «Старт»")
    return card


def _check_ready() -> None:
    if not telegram_service.telegram_enabled():
        raise ChecklistError("Бот не подключён")
    if not bot_sync_service.enabled():
        raise ChecklistError("Нет доступа к базе бота — бот не сможет принимать фото")


# ── Лист по тегу: не дошёл или человека не было в раздаче ──

def _person_by_tag(db: Session, username: str) -> tuple[int, dict] | None:
    tag = username.strip().lstrip("@").lower()
    if not tag:
        return None
    for tg_id, person in _people(db).items():
        if (person["username"] or "").lower() == tag:
            return tg_id, person
    return None


def _free_facts(db: Session, rng: random.Random | None = None) -> list[str]:
    """Три факта, которые в раздаче встречаются реже всего, — так баланс не съезжает."""
    cards = list_cards(db)
    pool = list(dict.fromkeys(f for c in cards for f in c.facts)) or list(DEFAULT_FACTS)
    counts = {f: 0 for f in pool}
    for card in cards:
        for fact in card.facts:
            counts[fact] += 1
    rng = rng or random.Random()
    rng.shuffle(pool)
    return sorted(pool, key=lambda f: counts[f])[:FACTS_PER_CARD]


def card_for_tag(db: Session, username: str) -> tuple[ChecklistCard, bool]:
    """Лист человека по тегу: уже есть — его же (дослать), нет — новый свободный.
    Второе значение — нужна ли картинка (её рисует админка)."""
    found = _person_by_tag(db, username)
    if found is None:
        raise ChecklistError(
            f"Бот не знает @{username.strip().lstrip('@')}. Пусть человек напишет боту /start "
            "(или что угодно в личку) — и попробуйте снова"
        )
    tg_id, person = found
    card = db.scalar(select(ChecklistCard).where(ChecklistCard.tg_id == tg_id))
    if card is None:
        number = (db.scalar(select(func.max(ChecklistCard.number))) or 0) + 1
        card = ChecklistCard(
            tg_id=tg_id, number=number, full_name=person["name"], username=person["username"],
            facts=_free_facts(db),
        )
        db.add(card)
        db.commit()
        db.refresh(card)
    return card, not card.image_ready


def send_one(db: Session, card_id: int) -> ChecklistCard:
    _check_ready()
    card = db.get(ChecklistCard, card_id)
    if card is None:
        raise ChecklistError("Чек-лист не найден")
    data = image(db, card.id)
    if data is None:
        raise ChecklistError("Картинка листа не готова")
    _deliver(db, card, data)
    if card.status != ChecklistStatus.SENT:
        raise ChecklistError("Telegram не принял — пусть человек откроет бота и нажмёт «Старт»")
    return card


def is_sending() -> bool:
    return _sending


def start_sending(db: Session) -> None:
    global _sending
    _check_ready()
    cards = [c for c in list_cards(db) if c.status != ChecklistStatus.SENT]
    if not cards:
        raise ChecklistError("Нечего отправлять — сначала подготовьте чек-листы")
    if any(not c.image_ready for c in cards):
        raise ChecklistError("Не все картинки готовы — подготовьте чек-листы ещё раз")
    with _send_lock:
        if _sending:
            raise ChecklistError("Уже рассылаем")
        _sending = True
    _spawn(_run, [c.id for c in cards])


def _spawn(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def _run(card_ids: list[int]) -> None:
    global _sending
    db = SessionLocal()
    try:
        for card_id in card_ids:
            card = db.get(ChecklistCard, card_id)
            data = image(db, card_id)
            if card is None or data is None or card.status == ChecklistStatus.SENT:
                continue
            _deliver(db, card, data)
            time.sleep(SEND_INTERVAL)
    except Exception:
        logger.exception("Рассылка чек-листов оборвалась")
    finally:
        db.close()
        with _send_lock:
            _sending = False


def reset(db: Session) -> None:
    """Начать заново: убрать листы, картинки и приём фото в боте."""
    if _sending:
        raise ChecklistError("Идёт рассылка — дождитесь конца")
    db.execute(delete(ChecklistCard))
    db.commit()
    _clear_images()
    _bot_drop()
