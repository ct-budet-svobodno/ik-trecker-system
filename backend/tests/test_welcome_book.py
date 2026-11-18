from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.core.config import settings
from app.services import welcome_book_service as service


def headers(client, credentials):
    token = client.post("/api/auth/login", data=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_pdf(pages=2, password=None):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if password:
        writer.encrypt(password)
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


@pytest.fixture
def book_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "welcome_book_dir", str(tmp_path))
    return tmp_path


def test_bundled_book_available_to_members(client, employee_credentials, book_dir):
    auth = headers(client, employee_credentials)
    assert client.get("/api/welcome-book").status_code == 401
    assert client.get("/api/welcome-book/pdf").status_code == 401
    info = client.get("/api/welcome-book", headers=auth).json()
    assert info["available"] and info["pages"] == 42
    response = client.get("/api/welcome-book/pdf", headers=auth)
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
    assert response.headers["cache-control"] == "private, no-store"


def test_only_admin_can_replace_book(client, admin_credentials, employee_credentials, book_dir):
    admin = headers(client, admin_credentials)
    member = headers(client, employee_credentials)
    pdf = make_pdf()
    old = client.get("/api/welcome-book", headers=member).json()
    assert client.put("/api/welcome-book", headers=member, content=pdf).status_code == 403
    response = client.put("/api/welcome-book", headers=admin, content=pdf)
    assert response.status_code == 200
    assert response.json()["pages"] == 2
    assert response.json()["version"] != old["version"]
    assert client.get("/api/welcome-book/pdf", headers=member).content == pdf
    assert (book_dir / "welcome-book.pdf").read_bytes() == pdf
    assert not list(book_dir.glob("*.tmp"))


@pytest.mark.parametrize("bad_pdf", [b"not a pdf", b"%PDF-broken", make_pdf(password="secret")])
def test_invalid_pdf_keeps_previous_edition(client, admin_credentials, book_dir, bad_pdf):
    auth = headers(client, admin_credentials)
    good = make_pdf()
    service.publish(good)
    response = client.put("/api/welcome-book", headers=auth, content=bad_pdf)
    assert response.status_code == 422
    assert (book_dir / "welcome-book.pdf").read_bytes() == good


def test_upload_limit(client, admin_credentials, book_dir, monkeypatch):
    monkeypatch.setattr(service, "MAX_BYTES", 32)
    response = client.put("/api/welcome-book", headers=headers(client, admin_credentials), content=b"x" * 33)
    assert response.status_code == 413
    assert not (book_dir / "welcome-book.pdf").exists()


def test_page_count_limit(book_dir, monkeypatch):
    monkeypatch.setattr(service, "MAX_PAGES", 1)
    with pytest.raises(ValueError, match="страниц"):
        service.publish(make_pdf(2))
    assert not (book_dir / "welcome-book.pdf").exists()


def test_readers_access_and_unopened_members(client, admin_credentials, employee_credentials, book_dir):
    admin = headers(client, admin_credentials)
    member = headers(client, employee_credentials)
    assert client.get("/api/welcome-book/readers").status_code == 401
    assert client.get("/api/welcome-book/readers", headers=member).status_code == 403
    # Метаданные и скачивание PDF ещё не означают, что просмотрщик открылся.
    client.get("/api/welcome-book/pdf", headers=member)
    rows = client.get("/api/welcome-book/readers", headers=admin).json()["readers"]
    assert {row["username"] for row in rows} == {"admin", "employee"}
    assert all(row["max_page"] == row["percent"] == 0 for row in rows)
    assert all(row["first_opened_at"] is None for row in rows)


def test_progress_is_personal_and_never_decreases(client, admin_credentials, employee_credentials, book_dir):
    admin = headers(client, admin_credentials)
    member = headers(client, employee_credentials)
    version = client.get("/api/welcome-book", headers=member).json()["version"]
    def record(page):
        return client.put("/api/welcome-book/progress", headers=member, json={"version": version, "page": page, "user_id": 1})
    assert record(1).status_code == 204
    first = client.get("/api/welcome-book/readers", headers=admin).json()
    employee = next(row for row in first["readers"] if row["username"] == "employee")
    assert employee["max_page"] == 1
    assert employee["first_opened_at"].endswith("Z") or employee["first_opened_at"].endswith("+00:00")
    assert record(20).status_code == 204
    assert record(3).status_code == 204
    latest = client.get("/api/welcome-book/readers", headers=admin).json()
    employee_latest = next(row for row in latest["readers"] if row["username"] == "employee")
    assert employee_latest["max_page"] == 20 and employee_latest["percent"] == 48
    assert employee_latest["first_opened_at"] == employee["first_opened_at"]
    assert employee_latest["last_seen_at"] >= employee["last_seen_at"]
    assert next(row for row in latest["readers"] if row["username"] == "admin")["max_page"] == 0
    assert record(42).status_code == 204
    assert next(row for row in client.get("/api/welcome-book/readers", headers=admin).json()["readers"] if row["username"] == "employee")["percent"] == 100


def test_new_edition_has_separate_progress(client, admin_credentials, book_dir):
    admin = headers(client, admin_credentials)
    old_version = client.get("/api/welcome-book", headers=admin).json()["version"]
    assert client.put("/api/welcome-book/progress", headers=admin, json={"version": old_version, "page": 42}).status_code == 204
    new = client.put("/api/welcome-book", headers=admin, content=make_pdf()).json()
    assert client.get("/api/welcome-book/readers", headers=admin).json()["readers"][0]["max_page"] == 0
    assert client.put("/api/welcome-book/progress", headers=admin, json={"version": old_version, "page": 1}).status_code == 409
    assert client.put("/api/welcome-book/progress", headers=admin, json={"version": new["version"], "page": 2}).status_code == 204
    assert client.get("/api/welcome-book/readers", headers=admin).json()["readers"][0]["percent"] == 100
    from tests.conftest import TestingSessionLocal
    from app.models.welcome_book import WelcomeBookProgress
    from sqlalchemy import select
    with TestingSessionLocal() as db:
        assert len(list(db.scalars(select(WelcomeBookProgress)))) == 2


@pytest.mark.parametrize("page", [0, -1, 301, 1.5, True])
def test_invalid_progress_page(client, employee_credentials, book_dir, page):
    member = headers(client, employee_credentials)
    version = client.get("/api/welcome-book", headers=member).json()["version"]
    assert client.put("/api/welcome-book/progress", headers=member, json={"version": version, "page": page}).status_code == 422


def test_progress_authentication_and_document_bounds(client, employee_credentials, book_dir):
    assert client.put("/api/welcome-book/progress", json={"version": "a" * 64, "page": 1}).status_code == 401
    member = headers(client, employee_credentials)
    info = service.publish(make_pdf())
    assert client.put("/api/welcome-book/progress", headers=member, json={"version": info["version"], "page": 3}).status_code == 409
    assert client.put("/api/welcome-book/progress", headers=member, json={"version": "a" * 64, "page": 1}).status_code == 409
