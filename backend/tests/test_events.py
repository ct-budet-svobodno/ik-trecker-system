def _login(client, credentials):
    response = client.post("/api/auth/login", data=credentials)
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_event(client, admin_credentials):
    token = _login(client, admin_credentials)
    response = client.post(
        "/api/events",
        json={"title": "Весенний концерт", "start_at": "2027-06-15T19:00:00"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Весенний концерт"
    assert body["end_at"] is None


def test_manager_can_create_event(client, manager_credentials):
    token = _login(client, manager_credentials)
    response = client.post(
        "/api/events",
        json={"title": "Фестиваль ИК-Осень", "start_at": "2027-09-10T12:00:00"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201


def test_employee_cannot_create_event(client, employee_credentials):
    token = _login(client, employee_credentials)
    response = client.post(
        "/api/events",
        json={"title": "Не моё дело", "start_at": "2027-01-01T10:00:00"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_employee_can_list_events(client, admin_credentials, employee_credentials):
    admin_token = _login(client, admin_credentials)
    created = client.post(
        "/api/events",
        json={"title": "Открытие выставки", "start_at": "2027-05-14T15:00:00"},
        headers=_auth_headers(admin_token),
    ).json()

    employee_token = _login(client, employee_credentials)
    response = client.get("/api/events", headers=_auth_headers(employee_token))
    assert response.status_code == 200
    assert any(event["id"] == created["id"] for event in response.json())


def test_admin_can_update_event(client, admin_credentials):
    token = _login(client, admin_credentials)
    created = client.post(
        "/api/events",
        json={"title": "Встреча", "start_at": "2027-03-01T10:00:00"},
        headers=_auth_headers(token),
    ).json()

    response = client.patch(
        f"/api/events/{created['id']}",
        json={"location": "Конференц-зал", "end_at": "2027-03-01T11:00:00"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["location"] == "Конференц-зал"
    assert body["end_at"] is not None


def test_employee_cannot_update_or_delete_event(client, admin_credentials, employee_credentials):
    admin_token = _login(client, admin_credentials)
    created = client.post(
        "/api/events",
        json={"title": "Встреча", "start_at": "2027-03-01T10:00:00"},
        headers=_auth_headers(admin_token),
    ).json()

    employee_token = _login(client, employee_credentials)
    patch_response = client.patch(
        f"/api/events/{created['id']}",
        json={"title": "Подмена"},
        headers=_auth_headers(employee_token),
    )
    assert patch_response.status_code == 403

    delete_response = client.delete(
        f"/api/events/{created['id']}", headers=_auth_headers(employee_token)
    )
    assert delete_response.status_code == 403


def test_admin_can_delete_event(client, admin_credentials):
    token = _login(client, admin_credentials)
    created = client.post(
        "/api/events",
        json={"title": "Отменённое мероприятие", "start_at": "2027-04-01T10:00:00"},
        headers=_auth_headers(token),
    ).json()

    delete_response = client.delete(f"/api/events/{created['id']}", headers=_auth_headers(token))
    assert delete_response.status_code == 204

    list_response = client.get("/api/events", headers=_auth_headers(token))
    assert all(event["id"] != created["id"] for event in list_response.json())


def test_time_is_kept_as_wall_clock(client, admin_credentials):
    # Время уходит и возвращается теми же цифрами: раньше «Z» сдвигал его назад
    # на каждом сохранении (SQLite пояс не хранит, фронт читал время как местное).
    headers = _auth_headers(_login(client, admin_credentials))
    created = client.post(
        "/api/events",
        json={"title": "Адаптация", "start_at": "2027-10-30T18:00:00+05:00", "end_at": "2027-10-30T20:30:00"},
        headers=headers,
    ).json()
    assert (created["start_at"], created["end_at"]) == ("2027-10-30T18:00:00", "2027-10-30T20:30:00")
    for _ in range(2):
        again = client.patch(
            f"/api/events/{created['id']}", json={"start_at": created["start_at"]}, headers=headers
        ).json()
        assert again["start_at"] == "2027-10-30T18:00:00"


def test_rsvp(client, admin_credentials, employee_credentials, manager_credentials):
    admin = _auth_headers(_login(client, admin_credentials))
    employee = _auth_headers(_login(client, employee_credentials))
    manager = _auth_headers(_login(client, manager_credentials))
    event_id = client.post(
        "/api/events", json={"title": "Собрание", "start_at": "2027-03-01T18:00:00"}, headers=admin
    ).json()["id"]
    url = f"/api/events/{event_id}/rsvp"

    # Отвечает любой, в том числе активист.
    going = client.put(url, json={"status": "going"}, headers=employee).json()
    assert going["my_rsvp"] == "going" and going["going_count"] == 1
    client.put(url, json={"status": "not_going"}, headers=manager)

    # Кто как ответил — видит только админ; остальным — счётчики.
    listed = next(e for e in client.get("/api/events", headers=admin).json() if e["id"] == event_id)
    assert listed["my_rsvp"] is None
    assert [p["full_name"] for p in listed["going"]] == ["Олег Сотрудник"] and len(listed["not_going"]) == 1
    for headers in (employee, manager):
        seen = next(e for e in client.get("/api/events", headers=headers).json() if e["id"] == event_id)
        assert seen["going"] == [] and seen["not_going"] == []
        assert (seen["going_count"], seen["not_going_count"]) == (1, 1)

    # Передумал — ответ меняется, а не дублируется; null снимает.
    changed = client.put(url, json={"status": "not_going"}, headers=employee).json()
    assert (changed["going_count"], changed["not_going_count"]) == (0, 2)
    cleared = client.put(url, json={"status": None}, headers=employee).json()
    assert cleared["my_rsvp"] is None and cleared["not_going_count"] == 1

    assert client.put("/api/events/999/rsvp", json={"status": "going"}, headers=employee).status_code == 404
    assert client.delete(f"/api/events/{event_id}", headers=admin).status_code == 204
    from app.models.event_rsvp import EventRsvp
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    assert db.query(EventRsvp).count() == 0
    db.close()
