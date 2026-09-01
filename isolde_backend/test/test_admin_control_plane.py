from flask_jwt_extended import create_access_token

from app.models.auth_model import AuthSession
from app.models.api_key_model import ApiKey
from app.models.billing_model import CreditLedger, Invoice, PaymentEvent
from app.models.enterprise_models import AuditLog
from app.models.rag_model import RAGChunk, RAGDocument
from app.models.user import Setting, User
from app.models.workflow_model import Workflow, WorkflowExecution
from app.models.workspace_model import Workspace
from app.models.memory_model import UserMemory
from app.models.uploaded_file import UploadedFile
from app.models.codex_model import CodexProject, CodexProjectFile, CodexTask
from app.models.conversation import Conversation


def _user(db, email, role="Client"):
    user = User(name=role, email=email, role=role, status="Active", is_verified=True)
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(identity=user.id)}"}


def test_public_product_configuration_is_safe_and_has_truthful_defaults(client, db):
    db.session.add(Setting(key="openai_api_key", value="enc:never-public"))
    db.session.commit()
    response = client.get("/api/product/config")
    assert response.status_code == 200
    data = response.get_json()
    assert data["features"]["image"] is True
    assert data["assets"]["upload_status"] == "NOT_CONFIGURED"
    assert "never-public" not in response.get_data(as_text=True)


def test_admin_configuration_is_authorized_validated_persisted_and_audited(client, db):
    member = _user(db, "member-control@example.com")
    assert client.get("/api/admin/v1/configuration", headers=_headers(member)).status_code == 403

    admin = _user(db, "admin-control@example.com", "Admin")
    headers = _headers(admin)
    invalid = client.patch(
        "/api/admin/v1/configuration", headers=headers,
        json={"branding": {"announcement": "<script>bad</script>"}},
    )
    assert invalid.status_code == 400
    updated = client.patch(
        "/api/admin/v1/configuration", headers=headers,
        json={
            "features": {"marketplace": True, "video": False},
            "branding": {"application_name": "ISOLDE", "announcement": "Scheduled maintenance"},
        },
    )
    assert updated.status_code == 200
    public = client.get("/api/product/config").get_json()
    assert public["features"]["marketplace"] is True
    assert public["features"]["video"] is False
    assert public["branding"]["application_name"] == "ISOLDE"
    audit = AuditLog.query.filter_by(action="ADMIN_CONFIGURATION_UPDATE").one()
    assert audit.actor_user_id == admin.id
    assert "Scheduled maintenance" not in audit.details


def test_provider_control_is_effective_but_never_returns_secrets(client, db):
    admin = _user(db, "provider-admin@example.com", "Admin")
    db.session.add(Setting(key="openai_api_key", value="unit-" + "credential"))
    db.session.commit()
    headers = _headers(admin)
    changed = client.patch(
        "/api/admin/v1/providers/configuration", headers=headers,
        json={"active_provider": "openai", "models": {"openai": "gpt-4o-mini"}},
    )
    assert changed.status_code == 200
    current = client.get("/api/admin/v1/providers/configuration", headers=headers)
    assert current.status_code == 200
    assert current.get_json()["configuration"]["active_provider"] == "openai"
    assert current.get_json()["configuration"]["models"]["openai"] == "gpt-4o-mini"
    assert "api_key" not in current.get_data(as_text=True)
    assert client.post(
        "/api/admin/v1/providers/settings", headers=headers,
        json={"key": "arbitrary_setting", "value": "unsafe"},
    ).status_code == 400
    settings = client.get("/api/admin/v1/providers/settings", headers=headers)
    assert settings.status_code == 200
    assert "unit-credential" not in settings.get_data(as_text=True)

    unavailable = client.patch(
        "/api/admin/v1/providers/configuration", headers=headers,
        json={"active_provider": "claude"},
    )
    assert unavailable.status_code == 422
    assert unavailable.get_json()["capability"] == "NOT_CONFIGURED"


def test_admin_session_control_and_versioned_contract(client, app, db):
    admin = _user(db, "session-admin@example.com", "Admin")
    target = _user(db, "session-target@example.com")
    session = AuthSession.create(target.id, app.config["JWT_ACCESS_TOKEN_EXPIRES"])
    db.session.add(session)
    db.session.commit()
    headers = _headers(admin)
    assert client.get("/api/admin/v1/capabilities", headers=headers).status_code == 200
    assert client.get("/api/admin/v1/release", headers=headers).status_code == 200
    for path in (
        "/api/admin/v1/dashboard", "/api/admin/v1/users",
        "/api/admin/v1/organizations", "/api/admin/v1/projects",
        "/api/admin/v1/conversations", "/api/admin/v1/billing/summary",
        "/api/admin/v1/billing/subscriptions", "/api/admin/v1/providers/status",
        "/api/admin/v1/operations",
    ):
        assert client.get(path, headers=headers).status_code == 200
    listed = client.get(f"/api/admin/v1/users/{target.id}/sessions", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json()["sessions"][0]["active"] is True
    revoked = client.post(f"/api/admin/v1/users/{target.id}/sessions/revoke-all", headers=headers)
    assert revoked.status_code == 200
    assert revoked.get_json()["revoked_sessions"] == 1
    assert db.session.get(AuthSession, session.id).is_valid is False


def test_current_admin_session_is_safe_and_can_be_revoked(client, app, db):
    admin = _user(db, "current-session-admin@example.com", "Admin")
    member = _user(db, "current-session-member@example.com")
    assert client.get("/api/admin/v1/session", headers=_headers(member)).status_code == 403
    session = AuthSession.create(admin.id, app.config["JWT_ACCESS_TOKEN_EXPIRES"])
    db.session.add(session)
    db.session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(identity=admin.id, additional_claims={'sid': session.id})}"}
    current = client.get("/api/admin/v1/session", headers=headers)
    assert current.status_code == 200
    assert "user_agent_hash" not in current.get_data(as_text=True)
    assert client.delete("/api/admin/v1/session", headers=headers).status_code == 200
    assert db.session.get(AuthSession, session.id).revoked_at is not None
    assert AuditLog.query.filter_by(action="ADMIN_CURRENT_SESSION_REVOKED").count() == 1


def test_admin_financial_rag_workflow_inspection_is_paginated_and_safe(client, db):
    admin = _user(db, "inspection-admin@example.com", "Admin")
    owner = _user(db, "inspection-owner@example.com")
    workspace = Workspace(user_id=owner.id, name="Private workspace")
    db.session.add(workspace)
    db.session.flush()
    workflow = Workflow(workspace_id=workspace.id, name="Private workflow", is_active=True)
    document = RAGDocument(user_id=owner.id, filename="private.pdf", chunk_count=1)
    db.session.add_all([
        workflow, document,
        CreditLedger(user_id=owner.id, idempotency_key="ledger-inspection", credits_delta=-3, source="provider_usage", provider_tokens=50),
        PaymentEvent(provider="stripe", event_id="evt_inspection", event_type="invoice.paid"),
        Invoice(invoice_uid="invoice-inspection", user_id=owner.id, amount=12.0, status="generated"),
    ])
    db.session.flush()
    db.session.add_all([
        WorkflowExecution(workflow_id=workflow.id, status="NOT_SUPPORTED"),
        RAGChunk(document_id=document.id, user_id=owner.id, position=0, text="never expose this", embedding=[0.1], embedding_dimension=1),
    ])
    db.session.commit()
    headers = _headers(admin)
    for path, field in (
        ("/api/admin/v1/billing/ledger?page=1&page_size=1", "ledger"),
        ("/api/admin/v1/billing/events?page=1&page_size=1", "events"),
        ("/api/admin/v1/billing/invoices?page=1&page_size=1", "invoices"),
        ("/api/admin/v1/rag/documents?page=1&page_size=1", "documents"),
        ("/api/admin/v1/workflows?page=1&page_size=1", "workflows"),
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.get_json()["pagination"]["page_size"] == 1
        assert response.get_json()[field]
    detail = client.get(f"/api/admin/v1/rag/documents/{document.id}", headers=headers)
    assert detail.status_code == 200
    assert "never expose this" not in detail.get_data(as_text=True)
    assert client.patch(f"/api/admin/v1/workflows/{workflow.id}", headers=headers, json={"is_active": False}).status_code == 200
    assert AuditLog.query.filter_by(action="ADMIN_WORKFLOW_STATUS").count() == 1
    assert client.post("/api/admin/v1/billing/invoices/999/refund", headers=headers).status_code == 404


def test_super_admin_api_key_control_plane_is_safe_and_owner_aware(client, db):
    admin = _user(db, "key-admin@example.com", "Admin")
    super_admin = _user(db, "key-super-admin@example.com", "Super Admin")
    owner = _user(db, "key-owner@example.com")
    assert client.get("/api/admin/v1/api-keys", headers=_headers(admin)).status_code == 403

    created = client.post("/api/admin/v1/api-keys", headers=_headers(super_admin), json={
        "user_id": owner.id, "name": "Production integration", "permissions": "read,write", "expires_in_days": 30,
    })
    assert created.status_code == 201
    payload = created.get_json()
    assert payload["api_key"].startswith("isk_")
    assert payload["api_key"] not in str(payload["metadata"])
    record = db.session.get(ApiKey, payload["metadata"]["id"])
    assert record.key_hash != payload["api_key"]

    listed = client.get("/api/admin/v1/api-keys?page=1&page_size=1", headers=_headers(super_admin))
    assert listed.status_code == 200
    assert payload["api_key"] not in listed.get_data(as_text=True)
    assert listed.get_json()["keys"][0]["user_id"] == owner.id

    revoked = client.post(f"/api/admin/v1/api-keys/{record.id}/revoke", headers=_headers(super_admin))
    assert revoked.status_code == 200
    assert revoked.get_json()["idempotent"] is False
    assert db.session.get(ApiKey, record.id).is_revoked is True
    assert AuditLog.query.filter_by(action="ADMIN_API_KEY_REVOKE").count() == 1


def test_super_admin_control_plane_lists_and_protects_memory_files_coding_and_conversations(client, app, db):
    admin = _user(db, "gap-admin@example.com", "Admin")
    super_admin = _user(db, "gap-super@example.com", "Super Admin")
    owner = _user(db, "gap-owner@example.com")
    memory = UserMemory(user_id=owner.id, category="Profile", key="City", value="Private", memory="City: Private")
    uploaded = UploadedFile(user_id=owner.id, filename="private.txt", stored_path="users/x/private.txt", file_type="txt")
    project = CodexProject(user_id=owner.id, name="Private code")
    conversation = Conversation(user_id=owner.id, title="Private conversation")
    db.session.add_all([memory, uploaded, project, conversation])
    db.session.flush()
    db.session.add_all([CodexProjectFile(project_id=project.id, file_path="main.py", file_content="print('safe')", file_type="py", last_modified_by=owner.id), CodexTask(project_id=project.id, instruction="Describe", status="pending")])
    db.session.commit()
    assert client.get("/api/admin/v1/memory", headers=_headers(admin)).status_code == 403
    headers = _headers(super_admin)
    assert client.get("/api/admin/v1/memory?search=City&page_size=1", headers=headers).get_json()["memory"][0]["id"] == memory.id
    assert "Private" not in client.get("/api/admin/v1/memory", headers=headers).get_data(as_text=True)
    assert client.get("/api/admin/v1/files?page_size=1", headers=headers).get_json()["files"][0]["id"] == uploaded.id
    assert "stored_path" not in client.get("/api/admin/v1/files", headers=headers).get_data(as_text=True)
    assert client.get(f"/api/admin/v1/coding/projects/{project.id}/files", headers=headers).status_code == 200
    assert client.get(f"/api/admin/v1/coding/projects/{project.id}/tasks", headers=headers).status_code == 200
    assert client.get("/api/admin/v1/conversations?page=1&page_size=1&search=Private", headers=headers).get_json()["pagination"]["total"] == 1
    assert client.get("/api/admin/v1/audit?start_date=invalid", headers=headers).status_code == 400
