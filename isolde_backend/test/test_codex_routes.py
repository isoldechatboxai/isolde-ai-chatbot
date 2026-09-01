from app.models.codex_model import CodexProjectFile
from app.services.codex_service import apply_file_changes


def _headers(client, email):
    assert client.post("/api/register", json={"name": email, "email": email, "password": "StrongPass123!"}).status_code == 201
    token = client.post("/api/login", json={"email": email, "password": "StrongPass123!"}).get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _project(client, headers, name="Project"):
    response = client.post("/api/codex/projects", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.get_json()["data"]["id"]


def test_project_file_and_task_lifecycle(client):
    headers = _headers(client, "codex@example.com")
    project_id = _project(client, headers)
    assert client.patch(f"/api/codex/projects/{project_id}", headers=headers, json={"name": "Renamed", "description": "d"}).status_code == 200
    assert client.post(f"/api/codex/projects/{project_id}/files", headers=headers, json={"file_path": "src/a.py", "content": "x = 1\n"}).status_code == 201
    assert client.patch(f"/api/codex/projects/{project_id}/files/src/a.py", headers=headers, json={"new_file_path": "src/b.py"}).status_code == 200
    assert client.delete(f"/api/codex/projects/{project_id}/files/src/b.py", headers=headers).status_code == 200
    task = client.post(f"/api/codex/projects/{project_id}/tasks", headers=headers, json={"instruction": "add code"}).get_json()["data"]
    assert client.patch(f"/api/codex/projects/{project_id}/tasks/{task['id']}", headers=headers, json={"instruction": "updated"}).status_code == 200
    cancelled = client.post(f"/api/codex/projects/{project_id}/tasks/{task['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.get_json()["data"]["status"] == "cancelled"
    assert client.delete(f"/api/codex/projects/{project_id}", headers=headers).status_code == 200


def test_coding_ownership_and_path_security(client):
    owner = _headers(client, "owner@example.com")
    other = _headers(client, "other@example.com")
    project_id = _project(client, owner)
    assert client.get(f"/api/codex/projects/{project_id}", headers=other).status_code == 404
    assert client.post(f"/api/codex/projects/{project_id}/files", headers=other, json={"file_path": "x.py", "content": ""}).status_code == 404
    for unsafe in ("../secret.py", "..\\secret.py", "/tmp/x.py", "C:\\x.py", "x\x00.py"):
        response = client.post(f"/api/codex/projects/{project_id}/files", headers=owner, json={"file_path": unsafe, "content": ""})
        assert response.status_code == 400


def test_atomic_multi_file_changes_roll_back_on_validation_failure(client, db):
    headers = _headers(client, "atomic@example.com")
    project_id = _project(client, headers)
    user_id = client.get(f"/api/codex/projects/{project_id}", headers=headers).get_json()["data"]["user_id"]
    failure = apply_file_changes(user_id, project_id, [
        {"file_path": "first.py", "content": "one = 1\n"},
        {"file_path": "second.py", "content": "def broken(:\n"},
    ])
    assert failure["success"] is False
    assert CodexProjectFile.query.filter_by(project_id=project_id).count() == 0
    success = apply_file_changes(user_id, project_id, [
        {"file_path": "first.py", "content": "one = 1\n"},
        {"file_path": "second.txt", "content": "two"},
    ])
    assert success["success"] is True
    assert CodexProjectFile.query.filter_by(project_id=project_id).count() == 2
