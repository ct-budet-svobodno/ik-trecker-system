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


def test_manager_can_create_task(client, manager_credentials, direction):
    token = _login(client, manager_credentials)
    response = client.post(
        "/api/tasks",
        json={"title": "Райдер", "direction_id": direction.id},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201


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
    assert response.status_code == 403


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
