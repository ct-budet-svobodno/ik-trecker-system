def _login(client, credentials):
    return client.post("/api/auth/login", data=credentials).json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _board(client, token, title="Набор 2026"):
    return client.post("/api/zavod/boards", json={"title": title}, headers=_auth(token)).json()


def _node(client, token, board_id, title="Тема", **extra):
    payload = {"title": title, **extra}
    return client.post(
        f"/api/zavod/boards/{board_id}/nodes", json=payload, headers=_auth(token)
    ).json()


def test_employee_without_flag_gets_403(client, employee_credentials):
    token = _login(client, employee_credentials)
    assert client.get("/api/zavod/boards", headers=_auth(token)).status_code == 403


def test_flagged_employee_gets_access(client, admin_credentials, employee_credentials):
    admin_token = _login(client, admin_credentials)
    users = client.get("/api/users", headers=_auth(admin_token)).json()
    employee_id = next(u["id"] for u in users if u["username"] == "employee")
    client.patch(f"/api/users/{employee_id}", json={"is_zavod": True}, headers=_auth(admin_token))

    token = _login(client, employee_credentials)
    assert client.get("/api/zavod/boards", headers=_auth(token)).status_code == 200


def test_flagged_employee_sees_people_to_assign(client, admin_credentials, employee_credentials):
    """Список людей нужен всем внутри ZAVOD, хотя GET /users закрыт для сотрудника."""
    admin_token = _login(client, admin_credentials)
    users = client.get("/api/users", headers=_auth(admin_token)).json()
    employee_id = next(u["id"] for u in users if u["username"] == "employee")
    client.patch(f"/api/users/{employee_id}", json={"is_zavod": True}, headers=_auth(admin_token))

    token = _login(client, employee_credentials)
    assert client.get("/api/users", headers=_auth(token)).status_code == 403

    response = client.get("/api/zavod/users", headers=_auth(token))
    assert response.status_code == 200
    assert employee_id in [u["id"] for u in response.json()]


def test_board_returns_nodes_and_edges(client, admin_credentials):
    token = _login(client, admin_credentials)
    board = _board(client, token)
    first = _node(client, token, board["id"], "Первая", x=100, y=50)
    second = _node(client, token, board["id"], "Вторая", x=400, y=50)
    client.post(
        f"/api/zavod/boards/{board['id']}/edges",
        json={"source_id": first["id"], "target_id": second["id"]},
        headers=_auth(token),
    )

    detail = client.get(f"/api/zavod/boards/{board['id']}", headers=_auth(token)).json()
    assert detail["title"] == "Набор 2026"
    assert [n["title"] for n in detail["nodes"]] == ["Первая", "Вторая"]
    assert len(detail["edges"]) == 1
    assert detail["nodes"][0]["x"] == 100


def test_edge_to_itself_rejected(client, admin_credentials):
    token = _login(client, admin_credentials)
    board = _board(client, token)
    node = _node(client, token, board["id"])

    response = client.post(
        f"/api/zavod/boards/{board['id']}/edges",
        json={"source_id": node["id"], "target_id": node["id"]},
        headers=_auth(token),
    )
    assert response.status_code == 400


def test_duplicate_edge_rejected_in_both_directions(client, admin_credentials):
    token = _login(client, admin_credentials)
    board = _board(client, token)
    a = _node(client, token, board["id"], "A")
    b = _node(client, token, board["id"], "B")
    payload = {"source_id": a["id"], "target_id": b["id"]}
    assert (
        client.post(
            f"/api/zavod/boards/{board['id']}/edges", json=payload, headers=_auth(token)
        ).status_code
        == 201
    )

    # Обратная связь — та же самая, второй раз заводить нечего.
    reverse = {"source_id": b["id"], "target_id": a["id"]}
    response = client.post(
        f"/api/zavod/boards/{board['id']}/edges", json=reverse, headers=_auth(token)
    )
    assert response.status_code == 400


def test_edge_across_boards_rejected(client, admin_credentials):
    token = _login(client, admin_credentials)
    first_board = _board(client, token, "Первая доска")
    second_board = _board(client, token, "Вторая доска")
    here = _node(client, token, first_board["id"])
    there = _node(client, token, second_board["id"])

    response = client.post(
        f"/api/zavod/boards/{first_board['id']}/edges",
        json={"source_id": here["id"], "target_id": there["id"]},
        headers=_auth(token),
    )
    assert response.status_code == 400


def test_deleting_node_removes_its_edges(client, admin_credentials):
    token = _login(client, admin_credentials)
    board = _board(client, token)
    a = _node(client, token, board["id"], "A")
    b = _node(client, token, board["id"], "B")
    client.post(
        f"/api/zavod/boards/{board['id']}/edges",
        json={"source_id": a["id"], "target_id": b["id"]},
        headers=_auth(token),
    )

    assert client.delete(f"/api/zavod/nodes/{a['id']}", headers=_auth(token)).status_code == 204

    detail = client.get(f"/api/zavod/boards/{board['id']}", headers=_auth(token)).json()
    assert [n["title"] for n in detail["nodes"]] == ["B"]
    assert detail["edges"] == []


def test_bulk_move_updates_coordinates(client, admin_credentials):
    token = _login(client, admin_credentials)
    board = _board(client, token)
    a = _node(client, token, board["id"], "A", x=0, y=0)
    b = _node(client, token, board["id"], "B", x=0, y=0)

    response = client.post(
        f"/api/zavod/boards/{board['id']}/nodes/move",
        json={"moves": [{"id": a["id"], "x": 40, "y": 60}, {"id": b["id"], "x": 90, "y": 10}]},
        headers=_auth(token),
    )
    assert response.status_code == 200

    detail = client.get(f"/api/zavod/boards/{board['id']}", headers=_auth(token)).json()
    moved = {n["id"]: (n["x"], n["y"]) for n in detail["nodes"]}
    assert moved[a["id"]] == (40, 60)
    assert moved[b["id"]] == (90, 10)


def test_patch_touches_only_sent_fields(client, admin_credentials):
    """Частичное обновление не должно затирать соседние поля, а color=null — снимать цвет."""
    token = _login(client, admin_credentials)
    board = _board(client, token)
    node = _node(client, token, board["id"], "Тема", content="описание", color="#4caf6d")

    renamed = client.patch(
        f"/api/zavod/nodes/{node['id']}", json={"title": "Новое имя"}, headers=_auth(token)
    ).json()
    assert renamed["title"] == "Новое имя"
    assert renamed["content"] == "описание"
    assert renamed["color"] == "#4caf6d"

    cleared = client.patch(
        f"/api/zavod/nodes/{node['id']}", json={"color": None}, headers=_auth(token)
    ).json()
    assert cleared["color"] is None
    assert cleared["content"] == "описание"


def test_assignees_are_set_and_replaced(client, admin_credentials, employee_credentials):
    token = _login(client, admin_credentials)
    users = client.get("/api/users", headers=_auth(token)).json()
    employee_id = next(u["id"] for u in users if u["username"] == "employee")
    admin_id = next(u["id"] for u in users if u["username"] == "admin")

    board = _board(client, token)
    node = _node(client, token, board["id"], "Тема", assignee_ids=[employee_id])
    assert [a["id"] for a in node["assignees"]] == [employee_id]

    replaced = client.patch(
        f"/api/zavod/nodes/{node['id']}",
        json={"assignee_ids": [admin_id]},
        headers=_auth(token),
    ).json()
    assert [a["id"] for a in replaced["assignees"]] == [admin_id]

    cleared = client.patch(
        f"/api/zavod/nodes/{node['id']}", json={"assignee_ids": []}, headers=_auth(token)
    ).json()
    assert cleared["assignees"] == []


def test_unknown_color_rejected(client, admin_credentials):
    token = _login(client, admin_credentials)
    board = _board(client, token)
    response = client.post(
        f"/api/zavod/boards/{board['id']}/nodes",
        json={"title": "Тема", "color": "#123456"},
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_deleting_board_removes_its_contents(client, admin_credentials):
    token = _login(client, admin_credentials)
    board = _board(client, token)
    a = _node(client, token, board["id"], "A")
    b = _node(client, token, board["id"], "B")
    client.post(
        f"/api/zavod/boards/{board['id']}/edges",
        json={"source_id": a["id"], "target_id": b["id"]},
        headers=_auth(token),
    )

    assert client.delete(f"/api/zavod/boards/{board['id']}", headers=_auth(token)).status_code == 204
    assert client.get(f"/api/zavod/boards/{board['id']}", headers=_auth(token)).status_code == 404
    assert client.get("/api/zavod/boards", headers=_auth(token)).json() == []
