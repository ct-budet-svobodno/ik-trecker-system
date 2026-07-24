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


def test_editorial_row(client, admin_credentials, manager_credentials, direction, smi_direction):
    # direction = Дизайн, smi_direction = СМИ.
    admin_token = _login(client, admin_credentials)
    created = client.post(
        "/api/leadership-tasks",
        json={"title": "Спецвыпуск ко Дню ИК", "is_editorial": True, "date": DATE},
        headers=_auth_headers(admin_token),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["is_editorial"] is True
    assert body["direction_id"] is None

    # Руководитель СМИ ведёт задачи Редакции: ставит свои и закрывает существующие.
    head_id = client.post(
        "/api/users",
        json={
            "username": "smihead3",
            "password": "headpass123",
            "full_name": "Глава СМИ",
            "role": "employee",
        },
        headers=_auth_headers(admin_token),
    ).json()["id"]
    client.put(
        f"/api/directions/{smi_direction.id}/heads",
        json={"user_ids": [head_id]},
        headers=_auth_headers(admin_token),
    )
    head_token = _login(client, {"username": "smihead3", "password": "headpass123"})
    own = client.post(
        "/api/leadership-tasks",
        json={"title": "Разбор постов недели", "is_editorial": True, "date": DATE},
        headers=_auth_headers(head_token),
    )
    assert own.status_code == 201
    closed = client.patch(
        f"/api/leadership-tasks/{body['id']}",
        json={"status": "done"},
        headers=_auth_headers(head_token),
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "done"

    # Обычный менеджер (не руководитель СМИ/Дизайна, не тройка) — не может.
    manager_token = _login(client, manager_credentials)
    denied = client.post(
        "/api/leadership-tasks",
        json={"title": "нельзя", "is_editorial": True, "date": DATE},
        headers=_auth_headers(manager_token),
    )
    assert denied.status_code == 403

    # Редакция + направление одновременно — невалидно.
    both = client.post(
        "/api/leadership-tasks",
        json={"title": "X", "is_editorial": True, "direction_id": direction.id, "date": DATE},
        headers=_auth_headers(admin_token),
    )
    assert both.status_code == 422


def test_admin_can_create_position_block_with_span_and_color(client, admin_credentials):
    token = _login(client, admin_credentials)
    created = client.post(
        "/api/leadership-tasks",
        json={
            "title": "Блок четвёрки",
            "position": "chairman",
            "position_end": "first_deputy",
            "date": "2026-07-01",
            "end_date": "2026-07-03",
            "color": "#3d7de0",
        },
        headers=_auth_headers(token),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["position"] == "chairman"
    assert body["position_end"] == "first_deputy"
    assert body["end_date"] == "2026-07-03"
    assert body["color"] == "#3d7de0"


def test_position_end_must_not_precede_position(client, admin_credentials):
    token = _login(client, admin_credentials)
    # first_deputy идёт ниже secretary — как «верх» блока недопустим при низе secretary.
    resp = client.post(
        "/api/leadership-tasks",
        json={
            "title": "Перевёрнутый блок",
            "position": "first_deputy",
            "position_end": "secretary",
            "date": DATE,
        },
        headers=_auth_headers(token),
    )
    assert resp.status_code == 422


def test_unknown_color_rejected(client, admin_credentials):
    token = _login(client, admin_credentials)
    resp = client.post(
        "/api/leadership-tasks",
        json={"title": "X", "position": "chairman", "date": DATE, "color": "#123456"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 422


def test_block_listed_when_span_overlaps_window(client, admin_credentials):
    token = _login(client, admin_credentials)
    # Блок начинается до окна, но заходит в него концом — должен попасть в выборку.
    client.post(
        "/api/leadership-tasks",
        json={
            "title": "Заходящий блок",
            "position": "chairman",
            "date": "2026-06-29",
            "end_date": "2026-07-02",
        },
        headers=_auth_headers(token),
    )
    listing = client.get(
        "/api/leadership-tasks",
        params={"date_from": "2026-07-01", "date_to": "2026-07-07"},
        headers=_auth_headers(token),
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


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
