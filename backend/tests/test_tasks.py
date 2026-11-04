def _login(client, credentials):
    response = client.post("/api/auth/login", data=credentials)
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_task(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    response = client.post(
        "/api/tasks",
        json={"title": "Афиша", "description": "Сделать афишу", "direction_id": direction.id},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Афиша"
    assert body["direction"]["id"] == direction.id
    assert body["assignee"] is None


def _me(client, token):
    return client.get("/api/auth/me", headers=_auth_headers(token)).json()


def _make_head(client, admin_credentials, direction_id, user_token):
    """Назначить пользователя руководителем направления (через админа)."""
    admin = _auth_headers(_login(client, admin_credentials))
    user_id = _me(client, user_token)["id"]
    response = client.put(f"/api/directions/{direction_id}/heads", json={"user_ids": [user_id]}, headers=admin)
    assert response.status_code == 200, response.json()


def test_head_can_create_task_in_own_direction(client, admin_credentials, manager_credentials, direction):
    token = _login(client, manager_credentials)
    _make_head(client, admin_credentials, direction.id, token)
    response = client.post(
        "/api/tasks",
        json={"title": "Райдер", "direction_id": direction.id},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    assert response.json()["can_manage"] is True


def test_manager_cannot_create_task_in_foreign_direction(client, manager_credentials, direction):
    token = _login(client, manager_credentials)
    response = client.post(
        "/api/tasks",
        json={"title": "Райдер", "direction_id": direction.id},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_employee_cannot_create_task(client, employee_credentials, direction):
    token = _login(client, employee_credentials)
    response = client.post(
        "/api/tasks",
        json={"title": "Не моё дело", "direction_id": direction.id},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_employee_does_not_see_tasks_assigned_to_manager(
    client, admin_credentials, manager_credentials, employee_credentials, direction
):
    admin_token = _login(client, admin_credentials)

    manager_id = client.get("/api/users", headers=_auth_headers(admin_token)).json()
    manager_user = next(u for u in manager_id if u["username"] == "manager")
    employee_user = next(u for u in manager_id if u["username"] == "employee")

    task_for_manager = client.post(
        "/api/tasks",
        json={"title": "Задача менеджера", "direction_id": direction.id, "assignee_id": manager_user["id"]},
        headers=_auth_headers(admin_token),
    ).json()
    task_for_employee = client.post(
        "/api/tasks",
        json={"title": "Задача сотрудника", "direction_id": direction.id, "assignee_id": employee_user["id"]},
        headers=_auth_headers(admin_token),
    ).json()
    unassigned_task = client.post(
        "/api/tasks",
        json={"title": "Без исполнителя", "direction_id": direction.id},
        headers=_auth_headers(admin_token),
    ).json()

    employee_token = _login(client, employee_credentials)
    employee_view = client.get("/api/tasks", headers=_auth_headers(employee_token)).json()
    employee_ids = {t["id"] for t in employee_view}
    assert task_for_manager["id"] not in employee_ids
    assert task_for_employee["id"] in employee_ids
    assert unassigned_task["id"] in employee_ids

    admin_view = client.get("/api/tasks", headers=_auth_headers(admin_token)).json()
    admin_ids = {t["id"] for t in admin_view}
    assert {task_for_manager["id"], task_for_employee["id"], unassigned_task["id"]} <= admin_ids

    manager_token = _login(client, manager_credentials)
    manager_view = client.get("/api/tasks", headers=_auth_headers(manager_token)).json()
    manager_ids = {t["id"] for t in manager_view}
    assert task_for_manager["id"] in manager_ids


def test_employee_can_update_status_of_own_task(
    client, admin_credentials, employee_credentials, direction
):
    admin_token = _login(client, admin_credentials)
    employee_user = next(
        u
        for u in client.get("/api/users", headers=_auth_headers(admin_token)).json()
        if u["username"] == "employee"
    )
    task = client.post(
        "/api/tasks",
        json={"title": "Моя задача", "direction_id": direction.id, "assignee_id": employee_user["id"]},
        headers=_auth_headers(admin_token),
    ).json()

    employee_token = _login(client, employee_credentials)
    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "in_progress"},
        headers=_auth_headers(employee_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_employee_cannot_update_other_field_on_own_task(
    client, admin_credentials, employee_credentials, direction
):
    admin_token = _login(client, admin_credentials)
    employee_user = next(
        u
        for u in client.get("/api/users", headers=_auth_headers(admin_token)).json()
        if u["username"] == "employee"
    )
    task = client.post(
        "/api/tasks",
        json={"title": "Моя задача", "direction_id": direction.id, "assignee_id": employee_user["id"]},
        headers=_auth_headers(admin_token),
    ).json()

    employee_token = _login(client, employee_credentials)
    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Новое имя"},
        headers=_auth_headers(employee_token),
    )
    assert response.status_code == 403


def test_employee_cannot_update_task_assigned_to_someone_else(
    client, admin_credentials, manager_credentials, employee_credentials, direction
):
    admin_token = _login(client, admin_credentials)
    manager_user = next(
        u
        for u in client.get("/api/users", headers=_auth_headers(admin_token)).json()
        if u["username"] == "manager"
    )
    task = client.post(
        "/api/tasks",
        json={"title": "Задача менеджера", "direction_id": direction.id, "assignee_id": manager_user["id"]},
        headers=_auth_headers(admin_token),
    ).json()

    employee_token = _login(client, employee_credentials)
    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "done"},
        headers=_auth_headers(employee_token),
    )
    # ТЗ руководителя активисту не видно вовсе — не 403, а 404.
    assert response.status_code == 404


def test_admin_can_update_any_field_and_unassign(client, admin_credentials, employee_credentials, direction):
    admin_token = _login(client, admin_credentials)
    employee_user = next(
        u
        for u in client.get("/api/users", headers=_auth_headers(admin_token)).json()
        if u["username"] == "employee"
    )
    task = client.post(
        "/api/tasks",
        json={"title": "Задача", "direction_id": direction.id, "assignee_id": employee_user["id"]},
        headers=_auth_headers(admin_token),
    ).json()

    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Обновлённая задача", "status": "done", "assignee_id": None},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Обновлённая задача"
    assert body["status"] == "done"
    assert body["assignee"] is None



# ── Правка, удаление, обсуждение, видимость ──

def _admin_task(client, admin_credentials, direction, assignee_id=None, title="ТЗ"):
    token = _login(client, admin_credentials)
    return client.post(
        "/api/tasks",
        json={"title": title, "direction_id": direction.id, "assignee_id": assignee_id},
        headers=_auth_headers(token),
    ).json()


def test_head_edits_and_deletes_task_of_own_direction(
    client, admin_credentials, manager_credentials, employee_credentials, direction, smi_direction
):
    head_token = _login(client, manager_credentials)
    _make_head(client, admin_credentials, direction.id, head_token)
    employee_id = _me(client, _login(client, employee_credentials))["id"]
    task = _admin_task(client, admin_credentials, direction, employee_id)

    edited = client.patch(
        f"/api/tasks/{task['id']}", json={"title": "Новое", "priority": "high"}, headers=_auth_headers(head_token)
    )
    assert edited.status_code == 200 and edited.json()["title"] == "Новое"
    # В чужое направление не перенести.
    moved = client.patch(
        f"/api/tasks/{task['id']}", json={"direction_id": smi_direction.id}, headers=_auth_headers(head_token)
    )
    assert moved.status_code == 403
    # Исполнитель не удаляет.
    employee_token = _login(client, employee_credentials)
    assert client.delete(f"/api/tasks/{task['id']}", headers=_auth_headers(employee_token)).status_code == 403
    assert client.delete(f"/api/tasks/{task['id']}", headers=_auth_headers(head_token)).status_code == 204
    assert client.get("/api/tasks", headers=_auth_headers(head_token)).json() == []


def test_foreign_manager_cannot_edit(client, admin_credentials, manager_credentials, direction):
    task = _admin_task(client, admin_credentials, direction)
    token = _login(client, manager_credentials)
    response = client.patch(f"/api/tasks/{task['id']}", json={"title": "Чужое"}, headers=_auth_headers(token))
    assert response.status_code == 403
    listed = client.get("/api/tasks", headers=_auth_headers(token)).json()
    assert listed[0]["can_manage"] is False


def test_employee_cannot_open_manager_task_by_id(
    client, admin_credentials, manager_credentials, employee_credentials, direction
):
    manager_id = _me(client, _login(client, manager_credentials))["id"]
    task = _admin_task(client, admin_credentials, direction, manager_id)
    employee = _auth_headers(_login(client, employee_credentials))
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=employee).status_code == 404
    assert client.get(f"/api/tasks/{task['id']}/comments", headers=employee).status_code == 404


def test_task_comments(client, monkeypatch, admin_credentials, manager_credentials, employee_credentials, direction):
    sent = []
    monkeypatch.setattr(
        "app.services.push_service.send_to_users", lambda db, ids, **kw: sent.append((sorted(ids), kw))
    )
    employee_token = _login(client, employee_credentials)
    employee_id = _me(client, employee_token)["id"]
    admin_token = _login(client, admin_credentials)
    admin_id = _me(client, admin_token)["id"]
    task = _admin_task(client, admin_credentials, direction, employee_id)
    sent.clear()

    url = f"/api/tasks/{task['id']}/comments"
    first = client.post(url, json={"body": "Когда сдать?"}, headers=_auth_headers(employee_token))
    assert first.status_code == 201
    assert sent[-1][0] == [admin_id] and sent[-1][1]["url"] == f"/tasks?task={task['id']}"
    reply = client.post(url, json={"body": "К пятнице", "parent_id": first.json()["id"]}, headers=_auth_headers(admin_token))
    assert reply.json()["parent_id"] == first.json()["id"]

    # Посторонний руководитель читает, но не пишет.
    outsider = _auth_headers(_login(client, manager_credentials))
    assert len(client.get(url, headers=outsider).json()) == 2
    assert client.post(url, json={"body": "Я тоже"}, headers=outsider).status_code == 403

    listed = client.get("/api/tasks", headers=_auth_headers(employee_token)).json()
    assert listed[0]["comments_count"] == 2 and listed[0]["can_comment"] is True

    # Чужой комментарий исполнитель не удаляет; свой — вместе с ответами.
    assert client.delete(f"{url}/{reply.json()['id']}", headers=_auth_headers(employee_token)).status_code == 403
    assert client.delete(f"{url}/{first.json()['id']}", headers=_auth_headers(employee_token)).status_code == 204
    assert client.get(url, headers=outsider).json() == []
