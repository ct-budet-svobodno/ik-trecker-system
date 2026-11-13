from app.models.user import LeadershipPosition, UserRole
from app.schemas.user import UserCreate
from app.services import user_service
from tests.conftest import TestingSessionLocal


def _headers(client, credentials):
    token = client.post("/api/auth/login", data=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_any_user_assigns_checklist_to_any_other_user(client, employee_credentials, manager_credentials):
    issuer = _headers(client, employee_credentials)
    assignee = _headers(client, manager_credentials)
    assignee_id = client.get("/api/auth/me", headers=assignee).json()["id"]
    payload = {"title": "Подготовить афишу", "is_checklist": True, "assignee_id": assignee_id, "due_date": "2026-12-01"}

    issuer_id = client.get("/api/auth/me", headers=issuer).json()["id"]
    assert client.get("/api/users", headers=issuer).status_code == 403
    people = client.get("/api/users/checklist-assignees", headers=issuer).json()
    assert {person["id"] for person in people} == {issuer_id, assignee_id}
    assert all(set(person) == {"id", "full_name", "is_active"} for person in people)
    assert client.post("/api/tasks", json={"title": "Обычное ТЗ", "direction_id": 1}, headers=issuer).status_code == 403

    self_assignment = client.post("/api/tasks", json={**payload, "assignee_id": issuer_id}, headers=issuer)
    assert self_assignment.status_code == 400

    created = client.post("/api/tasks", json=payload, headers=issuer)
    assert created.status_code == 201
    task = created.json()
    assert task["status"] == "todo"
    assert task["is_checklist"] is True
    assert task["direction"] is None
    assert task["due_date"] == "2026-12-01"
    task_id = task["id"]

    assert client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=issuer).status_code == 403
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "in_review"}, headers=assignee).status_code == 403
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"}, headers=assignee).json()["status"] == "in_progress"
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=assignee).json()["status"] == "done"
    assert client.patch(f"/api/tasks/{task_id}", json={"due_date": None}, headers=issuer).status_code == 403
    assert client.patch(f"/api/tasks/{task_id}", json={"assignee_id": issuer_id}, headers=issuer).status_code == 400

    other_credentials = {"username": "otheremployee", "password": "password123"}
    db = TestingSessionLocal()
    try:
        user_service.create_user(db, UserCreate(full_name="Другой активист", role=UserRole.EMPLOYEE, **other_credentials))
    finally:
        db.close()
    other = _headers(client, other_credentials)
    assert client.get("/api/tasks", headers=other).json() == []
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=other).status_code == 404

    secretary_credentials = {"username": "secretary", "password": "password123"}
    db = TestingSessionLocal()
    try:
        secretary = user_service.create_user(
            db, UserCreate(full_name="Секретарь", role=UserRole.MANAGER, **secretary_credentials)
        )
        user_service.set_leadership_position(db, secretary, LeadershipPosition.SECRETARY)
    finally:
        db.close()
    secretary_headers = _headers(client, secretary_credentials)
    assert client.get("/api/tasks", headers=secretary_headers).json() == []
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=secretary_headers).status_code == 404


def test_checklist_requires_assignee_and_deadline(client, admin_credentials):
    admin = _headers(client, admin_credentials)
    response = client.post("/api/tasks", json={"title": "Без срока", "is_checklist": True}, headers=admin)
    assert response.status_code == 422
