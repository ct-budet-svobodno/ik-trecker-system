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
