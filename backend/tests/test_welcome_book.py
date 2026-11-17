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
