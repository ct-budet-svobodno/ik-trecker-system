import hashlib
from datetime import UTC
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories import welcome_book_repository

MAX_BYTES = 18 * 1024 * 1024
MAX_PAGES = 300


def book_path() -> Path:
    uploaded = Path(settings.welcome_book_dir) / "welcome-book.pdf"
    return uploaded if uploaded.is_file() else Path(__file__).resolve().parents[2] / "assets" / "welcome-book.pdf"


def describe(data: bytes) -> dict:
    if not data.startswith(b"%PDF-"):
        raise ValueError("Выберите PDF-файл")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("PDF должен быть без пароля")
        pages = len(reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Не удалось прочитать PDF-файл") from exc
    if not 1 <= pages <= MAX_PAGES:
        raise ValueError(f"В PDF должно быть от 1 до {MAX_PAGES} страниц")
    return {"available": True, "pages": pages, "version": hashlib.sha256(data).hexdigest()}


def metadata() -> dict:
    try:
        path = book_path()
        return {**describe(path.read_bytes()), "bundled": path.parent.name == "assets"}
    except FileNotFoundError:
        return {"available": False}


def publish(data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise ValueError("PDF должен быть не больше 18 МБ")
    info = describe(data)
    path = Path(settings.welcome_book_dir) / "welcome-book.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Параллельный читатель получает целиком старое или новое издание.
    temp_path = None
    try:
        with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(data)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return info


def record_progress(db: Session, user_id: int, version: str, page: int) -> None:
    info = metadata()
    if not info["available"] or version != info["version"]:
        raise ValueError("Издание велкомбука изменилось. Откройте раздел заново.")
    if page > info["pages"]:
        raise ValueError("Такой страницы в велкомбуке нет")
    welcome_book_repository.record(db, user_id, version, page)


def readers(db: Session) -> dict:
    info = metadata()
    if not info["available"]:
        return {"available": False, "readers": []}
    rows = []
    for user, progress in welcome_book_repository.list_readers(db, info["version"]):
        page = progress.max_page if progress else 0
        rows.append({
            "user_id": user.id, "full_name": user.full_name, "username": user.username,
            "max_page": page, "percent": 100 if page == info["pages"] else min(99, round(page / info["pages"] * 100)),
            "first_opened_at": progress.first_opened_at.replace(tzinfo=UTC) if progress else None,
            "last_seen_at": progress.last_seen_at.replace(tzinfo=UTC) if progress else None,
        })
    return {**info, "readers": rows}
