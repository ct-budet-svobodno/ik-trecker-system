def _login(client, credentials):
    response = client.post("/api/auth/login", data=credentials)
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_manager_can_create_and_list_notes(client, manager_credentials):
    token = _login(client, manager_credentials)
    create = client.post(
        "/api/leadership-notes",
        json={"title": "Совещание", "body": "Только для руководства"},
        headers=_auth_headers(token),
    )
    assert create.status_code == 201
    body = create.json()
    assert body["title"] == "Совещание"
    assert body["created_by"]["full_name"] == "Маша Менеджер"

    listing = client.get("/api/leadership-notes", headers=_auth_headers(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_admin_can_create_notes(client, admin_credentials):
    token = _login(client, admin_credentials)
    response = client.post(
        "/api/leadership-notes",
        json={"title": "Бюджет", "body": "секрет"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201


def test_employee_cannot_list_notes(client, employee_credentials):
    token = _login(client, employee_credentials)
    response = client.get("/api/leadership-notes", headers=_auth_headers(token))
    assert response.status_code == 403


def test_employee_cannot_create_notes(client, employee_credentials):
    token = _login(client, employee_credentials)
    response = client.post(
        "/api/leadership-notes",
        json={"title": "нельзя", "body": ""},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_anonymous_cannot_list_notes(client):
    response = client.get("/api/leadership-notes")
    assert response.status_code == 401


def test_admin_can_delete_note(client, admin_credentials):
    token = _login(client, admin_credentials)
    created = client.post(
        "/api/leadership-notes",
        json={"title": "Удалить меня", "body": ""},
        headers=_auth_headers(token),
    )
    note_id = created.json()["id"]

    deleted = client.delete(
        f"/api/leadership-notes/{note_id}", headers=_auth_headers(token)
    )
    assert deleted.status_code == 204

    listing = client.get("/api/leadership-notes", headers=_auth_headers(token))
    assert listing.json() == []
