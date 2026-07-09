def _login(client, credentials):
    response = client.post("/api/auth/login", data=credentials)
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_employee(client, admin_token, username, full_name):
    response = client.post(
        "/api/users",
        json={
            "username": username,
            "password": "employeepass1",
            "full_name": full_name,
            "role": "employee",
        },
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_admin_can_assign_heads(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    user_id = _create_employee(client, token, "designer", "Дизайнер Дизайнов")

    response = client.put(
        f"/api/directions/{direction.id}/heads",
        json={"user_ids": [user_id]},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    heads = response.json()["heads"]
    assert [h["id"] for h in heads] == [user_id]
    # Назначение руководителем повышает роль до manager.
    assert heads[0]["role"] == "manager"


def test_assigning_unknown_user_returns_422(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    response = client.put(
        f"/api/directions/{direction.id}/heads",
        json={"user_ids": [99999]},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_manager_cannot_assign_heads(client, admin_credentials, manager_credentials, direction):
    admin_token = _login(client, admin_credentials)
    user_id = _create_employee(client, admin_token, "designer2", "Второй Дизайнер")

    manager_token = _login(client, manager_credentials)
    response = client.put(
        f"/api/directions/{direction.id}/heads",
        json={"user_ids": [user_id]},
        headers=_auth_headers(manager_token),
    )
    assert response.status_code == 403


def test_heads_can_be_cleared(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    user_id = _create_employee(client, token, "designer3", "Третий Дизайнер")
    client.put(
        f"/api/directions/{direction.id}/heads",
        json={"user_ids": [user_id]},
        headers=_auth_headers(token),
    )

    cleared = client.put(
        f"/api/directions/{direction.id}/heads",
        json={"user_ids": []},
        headers=_auth_headers(token),
    )
    assert cleared.status_code == 200
    assert cleared.json()["heads"] == []
