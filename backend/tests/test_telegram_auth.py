import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.core.config import settings

BOT_TOKEN = "123456:TEST-token"
TG_USER = {"id": 777000111, "first_name": "Пётр", "username": "petr_ik"}


@pytest.fixture(autouse=True)
def telegram_token(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", BOT_TOKEN)
    # Тесты не должны ходить в настоящий Telegram.
    monkeypatch.setattr("app.services.telegram_service.telegram_enabled", lambda: False)


def _init_data(user=TG_USER, auth_date=None, token=BOT_TOKEN):
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def _login(client, credentials):
    return client.post("/api/auth/login", data=credentials).json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _tg_login(client, init_data):
    return client.post("/api/auth/telegram", json={"init_data": init_data})


def test_unlinked_telegram_gets_404(client, manager_credentials):
    assert _tg_login(client, _init_data()).status_code == 404


def test_link_then_login_without_password(client, manager_credentials):
    token = _login(client, manager_credentials)
    linked = client.post(
        "/api/auth/telegram/link", json={"init_data": _init_data()}, headers=_auth_headers(token)
    )
    assert linked.status_code == 200
    assert linked.json()["telegram_linked"] is True
    assert linked.json()["telegram_username"] == "petr_ik"

    response = _tg_login(client, _init_data())
    assert response.status_code == 200
    me = client.get("/api/auth/me", headers=_auth_headers(response.json()["access_token"]))
    assert me.json()["full_name"] == "Маша Менеджер"


def test_forged_signature_rejected(client, manager_credentials):
    token = _login(client, manager_credentials)
    client.post("/api/auth/telegram/link", json={"init_data": _init_data()}, headers=_auth_headers(token))
    forged = _init_data(token="999:other-bot")
    assert _tg_login(client, forged).status_code == 401


def test_stale_init_data_rejected(client, manager_credentials):
    token = _login(client, manager_credentials)
    client.post("/api/auth/telegram/link", json={"init_data": _init_data()}, headers=_auth_headers(token))
    old = _init_data(auth_date=int(time.time()) - 2 * 86400)
    assert _tg_login(client, old).status_code == 401


def test_relinking_moves_telegram_to_new_account(client, manager_credentials, employee_credentials):
    for credentials in (manager_credentials, employee_credentials):
        token = _login(client, credentials)
        client.post("/api/auth/telegram/link", json={"init_data": _init_data()}, headers=_auth_headers(token))

    access = _tg_login(client, _init_data()).json()["access_token"]
    me = client.get("/api/auth/me", headers=_auth_headers(access)).json()
    assert me["full_name"] == "Олег Сотрудник"


def test_unlink(client, manager_credentials):
    token = _login(client, manager_credentials)
    client.post("/api/auth/telegram/link", json={"init_data": _init_data()}, headers=_auth_headers(token))
    response = client.delete("/api/auth/telegram/link", headers=_auth_headers(token))
    assert response.json()["telegram_linked"] is False
    assert _tg_login(client, _init_data()).status_code == 404


def test_deactivated_user_cannot_enter_via_telegram(client, manager_credentials, admin_credentials):
    token = _login(client, manager_credentials)
    me = client.post(
        "/api/auth/telegram/link", json={"init_data": _init_data()}, headers=_auth_headers(token)
    ).json()
    client.patch(
        f"/api/users/{me['id']}",
        json={"is_active": False},
        headers=_auth_headers(_login(client, admin_credentials)),
    )
    assert _tg_login(client, _init_data()).status_code == 401
