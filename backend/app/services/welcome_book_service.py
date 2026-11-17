import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from pypdf import PdfReader

from app.core.config import settings

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
