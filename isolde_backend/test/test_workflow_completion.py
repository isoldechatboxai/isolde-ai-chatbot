from flask_jwt_extended import create_access_token

from app.models.user import User
from app.models.workspace_model import Workspace


def _workflow_owner(db):
    user = User(name="Workflow Owner", email="workflow@example.com", status="Active")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(user_id=user.id, name="Workflow Workspace")
    db.session.add(workspace)
    db.session.commit()
    return user, workspace


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(identity=user.id)}"}


def test_workflow_capabilities_are_truthful(client, db):
    user, workspace = _workflow_owner(db)
    headers = _headers(user)
    unsupported = client.post(
        "/api/workflows", headers=headers,
        json={"name": "Scheduled", "workspace_id": workspace.id, "trigger_type": "Scheduled"},
    )
    assert unsupported.status_code == 422
    assert unsupported.get_json()["status"] == "NOT_SUPPORTED"

    created = client.post(
        "/api/workflows", headers=headers,
        json={"name": "Manual", "workspace_id": workspace.id},
    )
    workflow_id = created.get_json()["workflow"]["id"]
    assert client.post(f"/api/workflows/{workflow_id}/execute", headers=headers).status_code == 501
    webhook = client.post(
        f"/api/workflows/{workflow_id}/webhooks", headers=headers,
        json={"endpoint_url": "http://127.0.0.1/internal", "secret_token": "do-not-store"},
    )
    assert webhook.status_code == 501
