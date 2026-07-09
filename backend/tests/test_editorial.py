DATE = "2026-07-01"


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


def _make_member(client, admin_token, username):
    user_id = _create_user(client, admin_token, username)
    client.patch(f"/api/users/{user_id}", json={"is_editorial": True}, headers=_auth(admin_token))
    return user_id


def _make_head(client, admin_token, username, direction_id):
    user_id = _create_user(client, admin_token, username)
    client.put(
        f"/api/directions/{direction_id}/heads",
        json={"user_ids": [user_id]},
        headers=_auth(admin_token),
    )
    return user_id


def _create_post(client, token, title="Карусель про набор", date=DATE):
    return client.post(
        "/api/editorial-posts",
        json={"date": date, "title": title, "format": "карусель", "brief": "суть"},
        headers=_auth(token),
    )


def test_editor_creates_and_lists(client, admin_credentials):
    token = _login(client, admin_credentials)
    created = _create_post(client, token)
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Карусель про набор"
    assert body["text_status"] == "empty"

    listing = client.get(
        "/api/editorial-posts",
        params={"date_from": DATE, "date_to": DATE},
        headers=_auth(token),
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_non_member_has_no_access(client, admin_credentials, employee_credentials):
    admin_token = _login(client, admin_credentials)
    _create_post(client, admin_token)
    token = _login(client, employee_credentials)
    assert (
        client.get(
            "/api/editorial-posts",
            params={"date_from": DATE, "date_to": DATE},
            headers=_auth(token),
        ).status_code
        == 403
    )
    assert _create_post(client, token).status_code == 403


def test_member_self_assigns_and_writes_text(client, admin_credentials):
    admin_token = _login(client, admin_credentials)
    _make_member(client, admin_token, "writer1")
    post_id = _create_post(client, admin_token).json()["id"]

    token = _login(client, {"username": "writer1", "password": "passw0rd1"})
    assigned = client.post(
        f"/api/editorial-posts/{post_id}/assign",
        json={"role": "writer"},
        headers=_auth(token),
    )
    assert assigned.status_code == 200
    body = assigned.json()
    assert body["writer"]["username"] == "writer1"
    # Назначение райтера переводит трек в «черновик».
    assert body["text_status"] == "draft"

    submitted = client.patch(
        f"/api/editorial-posts/{post_id}",
        json={"text_content": "Привет, мы объявляем набор!", "text_status": "review"},
        headers=_auth(token),
    )
    assert submitted.status_code == 200
    assert submitted.json()["text_status"] == "review"
    assert submitted.json()["text_content"].startswith("Привет")


def test_text_reviewer_comments_and_sets_status(client, admin_credentials, smi_direction):
    admin_token = _login(client, admin_credentials)
    _make_member(client, admin_token, "writer2")
    _make_head(client, admin_token, "smihead", smi_direction.id)
    post_id = _create_post(client, admin_token).json()["id"]

    writer_token = _login(client, {"username": "writer2", "password": "passw0rd1"})
    client.post(
        f"/api/editorial-posts/{post_id}/assign",
        json={"role": "writer"},
        headers=_auth(writer_token),
    )

    head_token = _login(client, {"username": "smihead", "password": "passw0rd1"})
    commented = client.post(
        f"/api/editorial-posts/{post_id}/comments",
        json={"target": "text", "body": "Уточни сроки в первом абзаце"},
        headers=_auth(head_token),
    )
    assert commented.status_code == 200
    assert len(commented.json()["comments"]) == 1

    fixed = client.patch(
        f"/api/editorial-posts/{post_id}",
        json={"text_status": "fixes"},
        headers=_auth(head_token),
    )
    assert fixed.status_code == 200
    assert fixed.json()["text_status"] == "fixes"


def test_design_reviewer_split_from_text(client, admin_credentials, direction, smi_direction):
    # direction = Дизайн, smi_direction = СМИ.
    admin_token = _login(client, admin_credentials)
    _make_head(client, admin_token, "designhead", direction.id)
    _make_head(client, admin_token, "smihead2", smi_direction.id)
    post_id = _create_post(client, admin_token).json()["id"]

    design_token = _login(client, {"username": "designhead", "password": "passw0rd1"})
    ready = client.patch(
        f"/api/editorial-posts/{post_id}",
        json={"design_status": "ready"},
        headers=_auth(design_token),
    )
    assert ready.status_code == 200
    assert ready.json()["design_status"] == "ready"

    # Руководитель СМИ — ревьюер текста, но НЕ дизайна.
    smi_token = _login(client, {"username": "smihead2", "password": "passw0rd1"})
    denied = client.patch(
        f"/api/editorial-posts/{post_id}",
        json={"design_status": "ready"},
        headers=_auth(smi_token),
    )
    assert denied.status_code == 403


def test_member_cannot_edit_post_meta(client, admin_credentials):
    admin_token = _login(client, admin_credentials)
    _make_member(client, admin_token, "member1")
    post_id = _create_post(client, admin_token).json()["id"]

    token = _login(client, {"username": "member1", "password": "passw0rd1"})
    resp = client.patch(
        f"/api/editorial-posts/{post_id}",
        json={"title": "взлом"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_isolated_from_general_board(client, admin_credentials):
    token = _login(client, admin_credentials)
    _create_post(client, token)
    assert client.get("/api/tasks", headers=_auth(token)).json() == []


def test_manager_can_view_calendar(client, admin_credentials, manager_credentials):
    admin_token = _login(client, admin_credentials)
    _create_post(client, admin_token)
    # Любой руководитель видит календарь Редакции (но не редактирует).
    token = _login(client, manager_credentials)
    listing = client.get(
        "/api/editorial-posts",
        params={"date_from": DATE, "date_to": DATE},
        headers=_auth(token),
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_assigned_outsider_sees_post_via_mine(client, admin_credentials, employee_credentials):
    admin_token = _login(client, admin_credentials)
    post_id = _create_post(client, admin_token).json()["id"]
    token = _login(client, employee_credentials)
    employee_id = client.get("/api/auth/me", headers=_auth(token)).json()["id"]

    # Редактор назначает обычного сотрудника (без флага Редакции) райтером.
    client.post(
        f"/api/editorial-posts/{post_id}/assign",
        json={"role": "writer", "user_id": employee_id},
        headers=_auth(admin_token),
    )

    # Сотрудник видит пост в «моих» и открывает карточку, но календарь ему закрыт.
    mine = client.get("/api/editorial-posts/mine", headers=_auth(token))
    assert mine.status_code == 200
    assert [p["id"] for p in mine.json()] == [post_id]
    assert client.get(f"/api/editorial-posts/{post_id}", headers=_auth(token)).status_code == 200
    assert (
        client.get(
            "/api/editorial-posts",
            params={"date_from": DATE, "date_to": DATE},
            headers=_auth(token),
        ).status_code
        == 403
    )
