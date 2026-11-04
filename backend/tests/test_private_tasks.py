from app.models.user import LeadershipPosition, UserRole
from app.schemas.user import UserCreate
from app.services import user_service
from tests.conftest import TestingSessionLocal


def _login(client, credentials):
    response = client.post("/api/auth/login", data=credentials)
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _me_id(client, token):
    return client.get("/api/auth/me", headers=_auth_headers(token)).json()["id"]


def _make_user(username, full_name, role, position=None):
    credentials = {"username": username, "password": "password123"}
    db = TestingSessionLocal()
    try:
        user = user_service.create_user(
            db, UserCreate(full_name=full_name, role=role, **credentials)
        )
        if position is not None:
            user_service.set_leadership_position(db, user, position)
    finally:
        db.close()
    return credentials


def _chairman():
    return _make_user("chairman", "Председатель Пётр", UserRole.MANAGER, LeadershipPosition.CHAIRMAN)


def _assign(client, token, assignee_id, title="Подготовить отчёт для ректората"):
    return client.post(
        "/api/tasks",
        json={"title": title, "is_private": True, "assignee_id": assignee_id},
        headers=_auth_headers(token),
    )


def _titles(client, credentials):
    token = _login(client, credentials)
    return [t["title"] for t in client.get("/api/tasks", headers=_auth_headers(token)).json()]


def test_chairman_assigns_private_task_without_direction(client, manager_credentials):
    chairman_token = _login(client, _chairman())
    manager_id = _me_id(client, _login(client, manager_credentials))

    response = _assign(client, chairman_token, manager_id)
    assert response.status_code == 201
    body = response.json()
    assert body["is_private"] is True
    assert body["direction"] is None
    assert body["assignee"]["id"] == manager_id
    assert body["created_by"]["full_name"] == "Председатель Пётр"


def test_private_task_visibility(
    client, manager_credentials, admin_credentials, employee_credentials
):
    chairman = _chairman()
    secretary = _make_user("secretary", "Секретарь Света", UserRole.MANAGER, LeadershipPosition.SECRETARY)
    deputy = _make_user("deputy", "Зам Зиновий", UserRole.MANAGER, LeadershipPosition.FIRST_DEPUTY)
    other_manager = _make_user("other", "Другой Руководитель", UserRole.MANAGER)
    manager_id = _me_id(client, _login(client, manager_credentials))
    _assign(client, _login(client, chairman), manager_id)

    expected = ["Подготовить отчёт для ректората"]
    # Автор, исполнитель, админы и секретарь видят поручение.
    assert _titles(client, chairman) == expected
    assert _titles(client, manager_credentials) == expected
    assert _titles(client, admin_credentials) == expected
    assert _titles(client, secretary) == expected
    # Остальные — нет, включая другие должности руководства.
    assert _titles(client, deputy) == []
    assert _titles(client, other_manager) == []
    assert _titles(client, employee_credentials) == []


def test_admin_sees_but_cannot_change_private_task(client, manager_credentials, admin_credentials):
    manager_id = _me_id(client, _login(client, manager_credentials))
    task_id = _assign(client, _login(client, _chairman()), manager_id).json()["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"status": "done"},
        headers=_auth_headers(_login(client, admin_credentials)),
    )
    assert response.status_code == 403


def test_ordinary_manager_cannot_give_private_task(client, manager_credentials, employee_credentials):
    token = _login(client, manager_credentials)
    employee_id = _me_id(client, _login(client, employee_credentials))
    assert _assign(client, token, employee_id).status_code == 403


def test_private_task_requires_assignee(client):
    token = _login(client, _chairman())
    response = client.post(
        "/api/tasks",
        json={"title": "Без исполнителя", "is_private": True},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_ordinary_task_still_requires_direction(client, admin_credentials):
    token = _login(client, admin_credentials)
    response = client.post("/api/tasks", json={"title": "Без направления"}, headers=_auth_headers(token))
    assert response.status_code == 422


def test_outsider_gets_404_on_private_task(client, manager_credentials):
    manager_id = _me_id(client, _login(client, manager_credentials))
    task_id = _assign(client, _login(client, _chairman()), manager_id).json()["id"]

    outsider_token = _login(client, _make_user("other", "Другой Руководитель", UserRole.MANAGER))
    response = client.patch(
        f"/api/tasks/{task_id}", json={"status": "done"}, headers=_auth_headers(outsider_token)
    )
    assert response.status_code == 404


def test_assignee_changes_only_status(client, manager_credentials):
    manager_id = _me_id(client, _login(client, manager_credentials))
    task_id = _assign(client, _login(client, _chairman()), manager_id).json()["id"]
    headers = _auth_headers(_login(client, manager_credentials))

    moved = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"}, headers=headers)
    assert moved.status_code == 200
    assert moved.json()["status"] == "in_progress"

    renamed = client.patch(f"/api/tasks/{task_id}", json={"title": "Другое"}, headers=headers)
    assert renamed.status_code == 403


def test_author_can_edit_and_reassign(client, manager_credentials):
    chairman_token = _login(client, _chairman())
    manager_id = _me_id(client, _login(client, manager_credentials))
    other_id = _me_id(client, _login(client, _make_user("other", "Другой Руководитель", UserRole.MANAGER)))
    task_id = _assign(client, chairman_token, manager_id).json()["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Отчёт к пятнице", "assignee_id": other_id},
        headers=_auth_headers(chairman_token),
    )
    assert response.status_code == 200
    assert response.json()["assignee"]["id"] == other_id
    # Прежний исполнитель поручение больше не видит.
    assert _titles(client, manager_credentials) == []


# ── Поручение нескольким руководителям ──

def _assign_many(client, token, assignee_ids, title="Отчёт к совету"):
    return client.post(
        "/api/tasks",
        json={"title": title, "is_private": True, "assignee_ids": assignee_ids},
        headers=_auth_headers(token),
    )


def _three_leaders(client, manager_credentials):
    first = _make_user("first", "Первый Зам", UserRole.MANAGER, LeadershipPosition.FIRST_DEPUTY)
    second = _make_user("second", "Рук Дизайна", UserRole.MANAGER)
    creds = [manager_credentials, first, second]
    ids = [_me_id(client, _login(client, c)) for c in creds]
    return creds, ids


def test_private_task_for_several_leaders(client, manager_credentials, employee_credentials):
    chairman_token = _login(client, _chairman())
    creds, ids = _three_leaders(client, manager_credentials)

    response = _assign_many(client, chairman_token, ids + [ids[0]])  # повтор отбрасывается
    assert response.status_code == 201
    body = response.json()
    assert [a["user"]["id"] for a in body["assignees"]] == ids
    assert all(a["status"] == "todo" for a in body["assignees"])
    assert body["assignee"]["id"] == ids[0]

    # Поручение видят все трое, активист — нет.
    for c in creds:
        assert _titles(client, c) == ["Отчёт к совету"]
    assert _titles(client, employee_credentials) == []


def test_each_assignee_moves_own_status(client, manager_credentials):
    chairman_token = _login(client, _chairman())
    creds, ids = _three_leaders(client, manager_credentials)
    task_id = _assign_many(client, chairman_token, ids).json()["id"]

    def patch(c, status):
        return client.patch(
            f"/api/tasks/{task_id}", json={"status": status}, headers=_auth_headers(_login(client, c))
        ).json()

    mine = patch(creds[0], "done")
    # Исполнитель видит свой статус, сводный — «в работе».
    assert mine["status"] == "done" and mine["overall_status"] == "in_progress"
    patch(creds[1], "in_review")
    assert patch(creds[2], "done")["overall_status"] == "in_review"

    author_view = client.get("/api/tasks", headers=_auth_headers(chairman_token)).json()[0]
    assert author_view["status"] == "in_review"
    assert {a["user"]["id"]: a["status"] for a in author_view["assignees"]} == {
        ids[0]: "done", ids[1]: "in_review", ids[2]: "done"
    }

    # Исполнитель не меняет чужое и не меняет состав.
    response = client.patch(
        f"/api/tasks/{task_id}", json={"assignee_ids": [ids[0]]}, headers=_auth_headers(_login(client, creds[0]))
    )
    assert response.status_code == 403

    # Автор принимает работу у всех.
    accepted = client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=_auth_headers(chairman_token)).json()
    assert accepted["status"] == "done" and all(a["status"] == "done" for a in accepted["assignees"])


def test_author_changes_assignees_keeping_statuses(client, manager_credentials):
    chairman_token = _login(client, _chairman())
    creds, ids = _three_leaders(client, manager_credentials)
    task_id = _assign_many(client, chairman_token, ids[:2]).json()["id"]
    client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"}, headers=_auth_headers(_login(client, creds[0])))

    updated = client.patch(
        f"/api/tasks/{task_id}", json={"assignee_ids": [ids[0], ids[2]]}, headers=_auth_headers(chairman_token)
    ).json()
    assert {a["user"]["id"]: a["status"] for a in updated["assignees"]} == {ids[0]: "in_progress", ids[2]: "todo"}
    assert _titles(client, creds[1]) == []  # убранный больше не видит


def test_unknown_assignee_rejected(client):
    response = _assign_many(client, _login(client, _chairman()), [99999])
    assert response.status_code == 400


def test_ordinary_task_cannot_have_several_assignees(client, admin_credentials, direction):
    token = _login(client, admin_credentials)
    response = client.post(
        "/api/tasks",
        json={"title": "ТЗ", "direction_id": direction.id, "assignee_ids": [1, 2]},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


# ── Напоминание и весточка автору ──

def _capture_push(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.push_service.send_to_users",
        lambda db, user_ids, **kw: sent.append((sorted(user_ids), kw)),
    )
    return sent


def test_author_reminds_only_those_not_done(client, monkeypatch, manager_credentials):
    sent = _capture_push(monkeypatch)
    chairman_token = _login(client, _chairman())
    creds, ids = _three_leaders(client, manager_credentials)
    task_id = _assign_many(client, chairman_token, ids).json()["id"]
    client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=_auth_headers(_login(client, creds[0])))
    client.patch(f"/api/tasks/{task_id}", json={"status": "in_review"}, headers=_auth_headers(_login(client, creds[2])))
    sent.clear()

    reminded = client.post(f"/api/tasks/{task_id}/remind", headers=_auth_headers(chairman_token))
    assert reminded.status_code == 200
    assert reminded.json()["reminded_at"].endswith(("Z", "+00:00"))
    assert sent[0][0] == [ids[1]]  # сделавшему и сдавшему на проверку не напоминаем
    assert sent[0][1]["url"] == f"/tasks?task={task_id}"

    # Сразу второй раз — пауза.
    again = client.post(f"/api/tasks/{task_id}/remind", headers=_auth_headers(chairman_token))
    assert again.status_code == 400 and "мин" in again.json()["detail"]

    # Исполнитель напоминать не может.
    by_assignee = client.post(f"/api/tasks/{task_id}/remind", headers=_auth_headers(_login(client, creds[1])))
    assert by_assignee.status_code == 400


def test_nothing_to_remind_when_all_done(client, manager_credentials):
    chairman_token = _login(client, _chairman())
    manager_id = _me_id(client, _login(client, manager_credentials))
    task_id = _assign(client, chairman_token, manager_id).json()["id"]
    client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=_auth_headers(_login(client, manager_credentials)))
    response = client.post(f"/api/tasks/{task_id}/remind", headers=_auth_headers(chairman_token))
    assert response.status_code == 400


def test_author_notified_when_assignee_submits(client, monkeypatch, manager_credentials):
    sent = _capture_push(monkeypatch)
    chairman_creds = _chairman()
    chairman_token = _login(client, chairman_creds)
    chairman_id = _me_id(client, chairman_token)
    manager_id = _me_id(client, _login(client, manager_credentials))
    task_id = _assign(client, chairman_token, manager_id).json()["id"]
    sent.clear()
    headers = _auth_headers(_login(client, manager_credentials))
    client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"}, headers=headers)
    assert sent == []  # «взял в работу» — без уведомления
    client.patch(f"/api/tasks/{task_id}", json={"status": "in_review"}, headers=headers)
    assert sent[-1][0] == [chairman_id] and "на проверку" in sent[-1][1]["title"]
