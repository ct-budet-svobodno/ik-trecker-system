import pytest

from app.core.config import settings
from app.services import registration_service
from tests.test_telegram_auth import BOT_TOKEN, TG_USER, _auth_headers, _init_data, _login, _tg_login

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2000


@pytest.fixture(autouse=True)
def telegram_env(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "telegram_bot_token", BOT_TOKEN)
    monkeypatch.setattr(settings, "profile_photos_dir", str(tmp_path / "photos"))
    monkeypatch.setattr("app.services.telegram_service.telegram_enabled", lambda: False)
    registration_service._link_codes.clear()


def _form(**overrides):
    data = {
        "init_data": _init_data(),
        "full_name": "Петров Пётр Петрович",
        "birthday": "2004-05-17",
        "study_group": "РИ-410015",
        "phone": "8 (999) 123-45-67",
        "email": "petr@urfu.me",
        "clothes_size": "M",
        "other_units": "Профбюро",
    }
    data.update(overrides)
    return data


def _register(client, photos=(JPEG, JPEG), **overrides):
    files = {f"photo{i}": (f"p{i}.jpg", data, "image/jpeg") for i, data in enumerate(photos, start=1)}
    return client.post("/api/auth/telegram/register", data=_form(**overrides), files=files)


def test_registration_waits_for_admin_then_logs_in(client, admin_credentials):
    options = client.get("/api/auth/telegram/registration-options").json()
    assert "M" in options["clothes_sizes"]

    assert _register(client).status_code == 201
    # До одобрения — «на рассмотрении», не 404 и не вход.
    pending = _tg_login(client, _init_data())
    assert pending.status_code == 403 and pending.json()["detail"]["code"] == "registration_pending"

    admin = _auth_headers(_login(client, admin_credentials))
    # В обычном списке пользователей заявки нет — она в /registrations.
    assert all(u["full_name"] != "Петров Пётр Петрович" for u in client.get("/api/users", headers=admin).json())
    registrations = client.get("/api/users/registrations", headers=admin).json()
    assert len(registrations) == 1
    reg = registrations[0]
    assert reg["telegram_username"] == TG_USER["username"]
    assert reg["profile"]["phone"] == "79991234567" and reg["profile"]["clothes_size"] == "M"
    photo = client.get(f"/api/users/{reg['id']}/photo/1", headers=admin)
    assert photo.status_code == 200 and photo.content == JPEG

    approved = client.post(f"/api/users/{reg['id']}/approve", headers=admin)
    assert approved.status_code == 200
    token = _tg_login(client, _init_data())
    assert token.status_code == 200
    me = client.get("/api/auth/me", headers=_auth_headers(token.json()["access_token"])).json()
    assert me["role"] == "employee" and me["telegram_linked"]
    # Повторно анкету не подать — аккаунт уже есть.
    assert _register(client).status_code == 400


def test_rejected_can_resubmit(client, admin_credentials):
    _register(client)
    admin = _auth_headers(_login(client, admin_credentials))
    user_id = client.get("/api/users/registrations", headers=admin).json()[0]["id"]
    client.post(f"/api/users/{user_id}/reject", headers=admin)
    rejected = _tg_login(client, _init_data())
    assert rejected.json()["detail"]["code"] == "registration_rejected"
    assert _register(client, full_name="Петров Пётр").status_code == 201
    assert _tg_login(client, _init_data()).json()["detail"]["code"] == "registration_pending"
    assert len(client.get("/api/users/registrations", headers=admin).json()) == 1


@pytest.mark.parametrize(
    "overrides, photos",
    [
        ({"phone": "123"}, (JPEG, JPEG)),
        ({"email": "нет"}, (JPEG, JPEG)),
        ({"full_name": "Петя"}, (JPEG, JPEG)),
        ({"clothes_size": "XXXXL"}, (JPEG, JPEG)),
        ({}, (b"not an image", JPEG)),
        ({"init_data": "hash=forged"}, (JPEG, JPEG)),
    ],
)
def test_bad_registration_rejected(client, overrides, photos):
    response = _register(client, photos=photos, **overrides)
    assert response.status_code in (400, 401)


def test_existing_account_links_by_code(client, manager_credentials):
    token = _login(client, manager_credentials)
    link = client.post("/api/auth/telegram/link-code", headers=_auth_headers(token)).json()
    assert len(link["code"]) == 10

    # Человек сначала по ошибке подал анкету — при привязке она исчезает.
    _register(client)
    claimed = client.post("/api/auth/telegram/claim", json={"init_data": _init_data(), "code": link["code"]})
    assert claimed.status_code == 200
    me = client.get("/api/auth/me", headers=_auth_headers(claimed.json()["access_token"])).json()
    assert me["username"] == manager_credentials["username"] and me["telegram_linked"]
    assert _tg_login(client, _init_data()).status_code == 200

    # Код одноразовый.
    again = client.post("/api/auth/telegram/claim", json={"init_data": _init_data(), "code": link["code"]})
    assert again.status_code == 400


def test_aktiv_and_directions_in_users_list(client, admin_credentials, direction, smi_direction):
    assert _register(client, direction_id=str(direction.id)).status_code == 201
    admin = _auth_headers(_login(client, admin_credentials))
    reg = client.get("/api/users/registrations", headers=admin).json()[0]
    client.post(f"/api/users/{reg['id']}/approve", headers=admin)

    # Одобренная анкета — сразу в активе и с направлением из анкеты.
    petr = next(u for u in client.get("/api/users", headers=admin).json() if u["id"] == reg["id"])
    assert petr["is_activist"] and petr["direction_ids"] == [direction.id]
    # Заведённые вручную — не в активе, без направлений.
    others = [u for u in client.get("/api/users", headers=admin).json() if u["id"] != reg["id"]]
    assert not any(u["is_activist"] or u["direction_ids"] for u in others)

    from app.models.user_profile import UserProfile
    from tests.conftest import TestingSessionLocal

    def profile_direction():
        db = TestingSessionLocal()
        try:
            return db.get(UserProfile, reg["id"]).direction_id
        finally:
            db.close()

    # Несколько направлений; в анкете (одно) остаётся прежнее, раз оно в списке.
    both = client.patch(f"/api/users/{reg['id']}", json={"direction_ids": [smi_direction.id, direction.id]}, headers=admin)
    assert sorted(both.json()["direction_ids"]) == sorted([direction.id, smi_direction.id])
    assert profile_direction() == direction.id
    # Убрали направление анкеты — в анкете первое из новых.
    only_smi = client.patch(f"/api/users/{reg['id']}", json={"direction_ids": [smi_direction.id]}, headers=admin).json()
    assert only_smi["direction_ids"] == [smi_direction.id] and profile_direction() == smi_direction.id

    # Без direction_ids в запросе направления не трогаем; [] — снять все.
    renamed = client.patch(f"/api/users/{reg['id']}", json={"full_name": "Петров П."}, headers=admin).json()
    assert renamed["direction_ids"] == [smi_direction.id]
    off = client.patch(f"/api/users/{reg['id']}", json={"is_activist": False, "direction_ids": []}, headers=admin).json()
    assert not off["is_activist"] and off["direction_ids"] == [] and profile_direction() is None
    assert client.patch(f"/api/users/{reg['id']}", json={"direction_ids": [999]}, headers=admin).status_code == 400
