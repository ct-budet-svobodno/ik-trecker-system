def _login(client, credentials):
    return client.post("/api/auth/login", data=credentials).json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_user(client, admin_token, username, password="passw0rd1", role="employee"):
    return client.post(
        "/api/users",
        json={"username": username, "password": password, "full_name": username, "role": role},
        headers=_auth(admin_token),
    ).json()["id"]


def test_new_user_has_no_zavod_access(client, admin_credentials):
    admin_token = _login(client, admin_credentials)
    user_id = _create_user(client, admin_token, "novichok")

    users = client.get("/api/users", headers=_auth(admin_token)).json()
    created = next(u for u in users if u["id"] == user_id)
    assert created["is_zavod"] is False


def test_admin_grants_and_revokes_zavod(client, admin_credentials):
    admin_token = _login(client, admin_credentials)
    user_id = _create_user(client, admin_token, "zavodchanin")

    granted = client.patch(
        f"/api/users/{user_id}", json={"is_zavod": True}, headers=_auth(admin_token)
    )
    assert granted.status_code == 200
    assert granted.json()["is_zavod"] is True

    revoked = client.patch(
        f"/api/users/{user_id}", json={"is_zavod": False}, headers=_auth(admin_token)
    )
    assert revoked.status_code == 200
    assert revoked.json()["is_zavod"] is False


def test_zavod_flag_survives_unrelated_update(client, admin_credentials):
    """Правка ФИО не должна сбрасывать выданный доступ."""
    admin_token = _login(client, admin_credentials)
    user_id = _create_user(client, admin_token, "stabilnyi")
    client.patch(f"/api/users/{user_id}", json={"is_zavod": True}, headers=_auth(admin_token))

    updated = client.patch(
        f"/api/users/{user_id}", json={"full_name": "Новое ФИО"}, headers=_auth(admin_token)
    )
    assert updated.json()["is_zavod"] is True


def test_flag_reaches_own_profile(client, admin_credentials, employee_credentials):
    """От выдачи флага до /auth/me — на этом ответе держится гейт на фронте."""
    admin_token = _login(client, admin_credentials)
    employee_token = _login(client, employee_credentials)

    before = client.get("/api/auth/me", headers=_auth(employee_token)).json()
    assert before["is_zavod"] is False

    users = client.get("/api/users", headers=_auth(admin_token)).json()
    employee_id = next(u["id"] for u in users if u["username"] == "employee")
    client.patch(f"/api/users/{employee_id}", json={"is_zavod": True}, headers=_auth(admin_token))

    after = client.get("/api/auth/me", headers=_auth(employee_token)).json()
    assert after["is_zavod"] is True


def test_employee_cannot_grant_zavod(client, admin_credentials, employee_credentials):
    admin_token = _login(client, admin_credentials)
    user_id = _create_user(client, admin_token, "cel")
    employee_token = _login(client, employee_credentials)

    response = client.patch(
        f"/api/users/{user_id}", json={"is_zavod": True}, headers=_auth(employee_token)
    )
    assert response.status_code == 403
