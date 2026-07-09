def test_me_without_token_returns_401(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_login_success_and_me(client, admin_credentials):
    login_response = client.post("/api/auth/login", data=admin_credentials)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_login_wrong_password_returns_401(client, admin_credentials):
    response = client.post(
        "/api/auth/login",
        data={"username": admin_credentials["username"], "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_admin_can_create_user_but_employee_cannot(client, admin_credentials):
    admin_token = client.post("/api/auth/login", data=admin_credentials).json()["access_token"]

    create_response = client.post(
        "/api/users",
        json={
            "username": "employee1",
            "password": "employeepass1",
            "full_name": "Сотрудник Один",
            "role": "employee",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_response.status_code == 201

    employee_token = client.post(
        "/api/auth/login",
        data={"username": "employee1", "password": "employeepass1"},
    ).json()["access_token"]

    forbidden_response = client.post(
        "/api/users",
        json={
            "username": "employee2",
            "password": "employeepass2",
            "full_name": "Сотрудник Два",
            "role": "employee",
        },
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert forbidden_response.status_code == 403
