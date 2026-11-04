import pytest

from app.services import push_service

QUESTIONS = [
    {"id": "name", "type": "text", "title": "Как вас зовут?"},
    {"id": "about", "type": "textarea", "title": "О себе", "required": False},
    {"id": "dir", "type": "single", "title": "Направление", "options": ["ЦТ", "СМИ"]},
    {"id": "days", "type": "multi", "title": "Когда удобно", "options": ["Пн", "Ср", "Пт"]},
    {"id": "mood", "type": "scale", "title": "Настроение", "max": 5, "required": False},
]


def _auth(client, credentials):
    token = client.post("/api/auth/login", data=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _me(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


@pytest.fixture()
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(
        push_service, "send_to_users",
        lambda db, user_ids, **kw: calls.append((sorted(user_ids), kw["title"], kw["url"])),
    )
    return calls


def test_flow(client, admin_credentials, employee_credentials, manager_credentials, sent):
    admin = _auth(client, admin_credentials)
    employee = _auth(client, employee_credentials)
    manager = _auth(client, manager_credentials)
    employee_id, manager_id = _me(client, employee), _me(client, manager)

    # Собирать — только админ; кривые вопросы не пропускаем.
    assert client.post("/api/surveys", json={"title": "x", "questions": QUESTIONS}, headers=employee).status_code == 403
    bad = [{"id": "a", "type": "single", "title": "Один вариант", "options": ["да"]}]
    assert client.post("/api/surveys", json={"title": "x", "questions": bad}, headers=admin).status_code == 422
    survey = client.post(
        "/api/surveys", json={"title": "Сбор инфы", "description": "Коротко", "questions": QUESTIONS}, headers=admin
    ).json()
    sid = survey["id"]
    assert survey["status"] == "draft" and survey["can_edit_questions"]
    # Черновик получатель не видит, админ — может посмотреть.
    assert client.get(f"/api/surveys/{sid}/fill", headers=employee).status_code == 404
    assert client.get(f"/api/surveys/{sid}/fill", headers=admin).status_code == 200

    result = client.post(f"/api/surveys/{sid}/send", json={"user_ids": [employee_id]}, headers=admin).json()
    assert result == {"added": 1, "already": 0, "without_telegram": 1}
    assert sent == [([employee_id], "Новая анкета", f"/surveys/{sid}")]
    # Повторно тому же не шлём, новому — да.
    again = client.post(f"/api/surveys/{sid}/send", json={"user_ids": [employee_id, manager_id]}, headers=admin).json()
    assert (again["added"], again["already"]) == (1, 1) and sent[-1][0] == [manager_id]

    mine = client.get("/api/surveys/my", headers=employee).json()
    assert [s["id"] for s in mine] == [sid] and mine[0]["answers"] is None
    # Не получатель (админ не в списке) — в «моих» пусто.
    assert client.get("/api/surveys/my", headers=admin).json() == []

    url = f"/api/surveys/{sid}/response"
    missing = client.put(url, json={"answers": {"name": "Пётр"}}, headers=employee)
    assert missing.status_code == 400 and "Направление" in missing.json()["detail"]
    wrong = client.put(url, json={"answers": {"name": "П", "dir": "Фото", "days": ["Пн"]}}, headers=employee)
    assert wrong.status_code == 400
    scale = client.put(url, json={"answers": {"name": "П", "dir": "ЦТ", "days": ["Пн"], "mood": 9}}, headers=employee)
    assert scale.status_code == 400
    ok = client.put(
        url, json={"answers": {"name": " Пётр ", "dir": "ЦТ", "days": ["Пт", "Пн"], "mood": 4, "about": "", "junk": "x"}},
        headers=employee,
    ).json()
    assert ok["answers"] == {"name": "Пётр", "dir": "ЦТ", "days": ["Пн", "Пт"], "mood": 4}
    # Админ не получатель — ответить не может.
    assert client.put(url, json={"answers": {}}, headers=admin).status_code == 404

    # Ответы есть — вопросы не поменять, название — можно.
    view = client.get(f"/api/surveys/{sid}", headers=admin).json()
    assert not view["can_edit_questions"]
    answered = {r["user_id"]: r["answers"] for r in view["recipients"]}
    assert answered == {employee_id: ok["answers"], manager_id: None}
    changed = [*QUESTIONS[:-1]]
    assert client.put(f"/api/surveys/{sid}", json={"title": "x", "questions": changed}, headers=admin).status_code == 400
    renamed = client.put(f"/api/surveys/{sid}", json={"title": "Новое", "questions": QUESTIONS}, headers=admin)
    assert renamed.status_code == 200 and renamed.json()["title"] == "Новое"

    # Напоминание — только не ответившим, не чаще раза в 30 минут.
    assert client.post(f"/api/surveys/{sid}/remind", headers=admin).json() == {"reminded": 1}
    assert sent[-1][0] == [manager_id] and sent[-1][1] == "Напоминание: анкета"
    assert client.post(f"/api/surveys/{sid}/remind", headers=admin).status_code == 400

    summary = client.get("/api/surveys", headers=admin).json()
    assert (summary[0]["recipients"], summary[0]["responses"], summary[0]["questions_count"]) == (2, 1, 5)

    # Закрыта — ответы не принимаются, но видны.
    client.post(f"/api/surveys/{sid}/status", json={"status": "closed"}, headers=admin)
    closed = client.put(url, json={"answers": ok["answers"]}, headers=employee)
    assert closed.status_code == 400
    assert client.get(f"/api/surveys/{sid}/fill", headers=employee).json()["answers"]["dir"] == "ЦТ"

    assert client.delete(f"/api/surveys/{sid}", headers=admin).status_code == 204
    assert client.get("/api/surveys/my", headers=employee).json() == []
    from app.models.survey import SurveyRecipient, SurveyResponse
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    assert db.query(SurveyRecipient).count() == 0 and db.query(SurveyResponse).count() == 0
    db.close()
