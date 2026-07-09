DATE = "2026-07-01"


def _login(client, credentials):
    response = client.post("/api/auth/login", data=credentials)
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _me_id(client, token):
    return client.get("/api/auth/me", headers=_auth_headers(token)).json()["id"]


def _create(client, token, direction_id, title="План направления", date=DATE):
    return client.post(
        "/api/leadership-tasks",
        json={"title": title, "direction_id": direction_id, "date": date},
        headers=_auth_headers(token),
    )


def test_admin_can_create_and_list(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    created = _create(client, token, direction.id)
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "План направления"
    assert body["direction"]["short_code"] == "Дизайн"
    assert body["status"] == "todo"

    listing = client.get(
        "/api/leadership-tasks",
        params={"date_from": DATE, "date_to": DATE},
        headers=_auth_headers(token),
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_employee_has_no_access(client, employee_credentials, direction):
    token = _login(client, employee_credentials)
    assert _create(client, token, direction.id).status_code == 403
    listing = client.get(
        "/api/leadership-tasks",
        params={"date_from": DATE, "date_to": DATE},
        headers=_auth_headers(token),
    )
    assert listing.status_code == 403


def test_head_can_create_for_own_direction(client, admin_credentials, direction):
    admin_token = _login(client, admin_credentials)
    # Заводим сотрудника и назначаем руководителем направления (→ роль manager).
    user_id = client.post(
        "/api/users",
        json={
            "username": "head1",
            "password": "headpass123",
            "full_name": "Глава Дизайна",
            "role": "employee",
        },
        headers=_auth_headers(admin_token),
    ).json()["id"]
    client.put(
        f"/api/directions/{direction.id}/heads",
        json={"user_ids": [user_id]},
        headers=_auth_headers(admin_token),
    )

    head_token = _login(client, {"username": "head1", "password": "headpass123"})
    assert _create(client, head_token, direction.id).status_code == 201


def test_manager_cannot_create_for_foreign_direction(
    client, admin_credentials, manager_credentials, direction
):
    # manager_credentials — обычный менеджер, не руководитель этого направления.
    token = _login(client, manager_credentials)
    assert _create(client, token, direction.id).status_code == 403


def test_troika_can_create_for_any_direction(client, admin_credentials, manager_credentials, direction):
    admin_token = _login(client, admin_credentials)
    manager_id = _me_id(client, _login(client, manager_credentials))
    # Назначаем менеджеру должность тройки — теперь он ставит в любое направление.
    patched = client.patch(
        f"/api/users/{manager_id}",
        json={"leadership_position": "chairman"},
        headers=_auth_headers(admin_token),
    )
    assert patched.status_code == 200
    assert patched.json()["leadership_position"] == "chairman"

    token = _login(client, manager_credentials)
    assert _create(client, token, direction.id).status_code == 201


def test_troika_position_is_single_holder(client, admin_credentials, manager_credentials):
    admin_token = _login(client, admin_credentials)
    admin_id = _me_id(client, admin_token)
    manager_id = _me_id(client, _login(client, manager_credentials))

    client.patch(
        f"/api/users/{admin_id}",
        json={"leadership_position": "chairman"},
        headers=_auth_headers(admin_token),
    )
    client.patch(
        f"/api/users/{manager_id}",
        json={"leadership_position": "chairman"},
        headers=_auth_headers(admin_token),
    )
    # Должность перешла к менеджеру, у админа снялась.
    users = client.get("/api/users", headers=_auth_headers(admin_token)).json()
    by_id = {u["id"]: u for u in users}
    assert by_id[admin_id]["leadership_position"] is None
    assert by_id[manager_id]["leadership_position"] == "chairman"


def test_status_toggle(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    task_id = _create(client, token, direction.id).json()["id"]
    patched = client.patch(
        f"/api/leadership-tasks/{task_id}",
        json={"status": "done"},
        headers=_auth_headers(token),
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "done"


def test_isolated_from_general_board(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    _create(client, token, direction.id)
    # Запись таймлайна руководства не попадает в общую доску задач.
    tasks = client.get("/api/tasks", headers=_auth_headers(token)).json()
    assert tasks == []


def test_admin_can_create_position_task(client, admin_credentials):
    token = _login(client, admin_credentials)
    created = client.post(
        "/api/leadership-tasks",
        json={"title": "Совещание тройки", "position": "chairman", "date": DATE},
        headers=_auth_headers(token),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["position"] == "chairman"
    assert body["direction_id"] is None
    assert body["direction"] is None


def test_create_requires_exactly_one_target(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    # Ни направления, ни должности.
    neither = client.post(
        "/api/leadership-tasks",
        json={"title": "X", "date": DATE},
        headers=_auth_headers(token),
    )
    assert neither.status_code == 422
    # И то, и другое.
    both = client.post(
        "/api/leadership-tasks",
        json={"title": "X", "date": DATE, "direction_id": direction.id, "position": "chairman"},
        headers=_auth_headers(token),
    )
    assert both.status_code == 422


def test_head_cannot_create_position_task(client, admin_credentials, direction):
    admin_token = _login(client, admin_credentials)
    user_id = client.post(
        "/api/users",
        json={
            "username": "head2",
            "password": "headpass123",
            "full_name": "Глава без тройки",
            "role": "employee",
        },
        headers=_auth_headers(admin_token),
    ).json()["id"]
    client.put(
        f"/api/directions/{direction.id}/heads",
        json={"user_ids": [user_id]},
        headers=_auth_headers(admin_token),
    )
    head_token = _login(client, {"username": "head2", "password": "headpass123"})
    # Руководитель направления (не тройка) не может ставить задачи на должность.
    resp = client.post(
        "/api/leadership-tasks",
        json={"title": "нельзя", "position": "secretary", "date": DATE},
        headers=_auth_headers(head_token),
    )
    assert resp.status_code == 403


def test_admin_can_reset_password(client, admin_credentials):
    admin_token = _login(client, admin_credentials)
    user_id = client.post(
        "/api/users",
        json={"username": "resetme", "password": "oldpassword1", "full_name": "Сброс Паролев", "role": "employee"},
        headers=_auth_headers(admin_token),
    ).json()["id"]
    patched = client.patch(
        f"/api/users/{user_id}",
        json={"password": "newpassword1"},
        headers=_auth_headers(admin_token),
    )
    assert patched.status_code == 200
    assert client.post("/api/auth/login", data={"username": "resetme", "password": "oldpassword1"}).status_code == 401
    assert client.post("/api/auth/login", data={"username": "resetme", "password": "newpassword1"}).status_code == 200
