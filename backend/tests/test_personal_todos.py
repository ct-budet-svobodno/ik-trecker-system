TODAY = "2026-10-09"
YESTERDAY = "2026-10-08"


def _login(client, credentials):
    response = client.post("/api/auth/login", data=credentials)
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _add(client, token, title="Позвонить типографии", day=TODAY):
    return client.post(
        "/api/personal-todos",
        json={"title": title, "date": day},
        headers=_auth_headers(token),
    )


def _list(client, token, day=TODAY):
    return client.get(
        "/api/personal-todos", params={"date": day}, headers=_auth_headers(token)
    ).json()


def test_employee_can_create_and_list_own_day(client, employee_credentials):
    token = _login(client, employee_credentials)
    created = _add(client, token)
    assert created.status_code == 201
    assert created.json()["done"] is False

    _add(client, token, title="На завтра", day="2026-10-10")
    items = _list(client, token)
    assert [item["title"] for item in items] == ["Позвонить типографии"]


def test_requires_auth(client):
    assert client.get("/api/personal-todos", params={"date": TODAY}).status_code == 401


def test_list_is_private_per_user(client, employee_credentials, manager_credentials):
    employee_token = _login(client, employee_credentials)
    _add(client, employee_token)
    # Руководитель и админ чужой личный список не видят.
    assert _list(client, _login(client, manager_credentials)) == []


def test_cannot_touch_someone_elses_item(client, employee_credentials, admin_credentials):
    todo_id = _add(client, _login(client, employee_credentials)).json()["id"]
    admin_headers = _auth_headers(_login(client, admin_credentials))

    patched = client.patch(
        f"/api/personal-todos/{todo_id}", json={"done": True}, headers=admin_headers
    )
    assert patched.status_code == 404
    assert client.delete(f"/api/personal-todos/{todo_id}", headers=admin_headers).status_code == 404


def test_toggle_rename_and_delete(client, employee_credentials):
    token = _login(client, employee_credentials)
    todo_id = _add(client, token).json()["id"]

    patched = client.patch(
        f"/api/personal-todos/{todo_id}",
        json={"done": True, "title": "Позвонить в типографию"},
        headers=_auth_headers(token),
    )
    assert patched.status_code == 200
    assert patched.json()["done"] is True
    assert patched.json()["title"] == "Позвонить в типографию"

    assert client.delete(
        f"/api/personal-todos/{todo_id}", headers=_auth_headers(token)
    ).status_code == 204
    assert _list(client, token) == []


def test_empty_title_rejected(client, employee_credentials):
    token = _login(client, employee_credentials)
    assert _add(client, token, title="").status_code == 422


def test_carry_over_moves_only_undone_past_items(client, employee_credentials):
    token = _login(client, employee_credentials)
    undone_id = _add(client, token, title="Не успел", day=YESTERDAY).json()["id"]
    done_id = _add(client, token, title="Успел", day=YESTERDAY).json()["id"]
    client.patch(
        f"/api/personal-todos/{done_id}", json={"done": True}, headers=_auth_headers(token)
    )

    overdue = client.get(
        "/api/personal-todos/overdue", params={"before": TODAY}, headers=_auth_headers(token)
    ).json()
    assert [item["id"] for item in overdue] == [undone_id]

    moved = client.post(
        "/api/personal-todos/carry-over", json={"date": TODAY}, headers=_auth_headers(token)
    )
    assert moved.status_code == 200
    assert [item["id"] for item in moved.json()] == [undone_id]
    # Выполненное остаётся в своём дне.
    assert [item["id"] for item in _list(client, token, day=YESTERDAY)] == [done_id]
