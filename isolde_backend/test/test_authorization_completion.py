from flask_jwt_extended import create_access_token

from app.models.collaboration_model import Organization, OrganizationMember, OrganizationRole, OrganizationPolicy
from app.models.productivity_model import Task
from app.models.user import User
from app.models.workspace_model import Workspace, Project


def _user(db, email):
    user = User(name=email, email=email, status="Active")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(identity=user.id)}"}


def test_productivity_tasks_are_tenant_scoped(client, db):
    owner = _user(db, "task-owner@example.com")
    attacker = _user(db, "task-attacker@example.com")
    task = Task(user_id=owner.id, title="Private task")
    db.session.add(task)
    db.session.commit()

    assert client.get("/api/productivity/tasks", headers=_headers(attacker)).get_json()["tasks"] == []
    assert client.put(
        f"/api/productivity/tasks/{task.id}", headers=_headers(attacker), json={"title": "stolen"}
    ).status_code == 404
    assert client.delete(f"/api/productivity/tasks/{task.id}", headers=_headers(attacker)).status_code == 404


def test_productivity_rejects_foreign_workspace(client, db):
    owner = _user(db, "workspace-owner@example.com")
    attacker = _user(db, "workspace-attacker@example.com")
    workspace = Workspace(user_id=owner.id, name="Private")
    db.session.add(workspace)
    db.session.commit()
    response = client.post(
        "/api/productivity/tasks", headers=_headers(attacker),
        json={"title": "Intrusion", "workspace_id": workspace.id},
    )
    assert response.status_code == 404


def test_organization_membership_and_admin_permissions_are_enforced(client, db):
    owner = _user(db, "org-owner@example.com")
    member = _user(db, "org-member@example.com")
    attacker = _user(db, "org-attacker@example.com")
    org = Organization(name="Private Org", owner_id=owner.id)
    db.session.add(org)
    db.session.flush()
    viewer = OrganizationRole(org_id=org.id, name="Viewer", permissions="[]")
    db.session.add(viewer)
    db.session.flush()
    db.session.add(OrganizationMember(org_id=org.id, user_id=member.id, role_id=viewer.id))
    db.session.commit()

    assert client.get(f"/api/organizations/{org.id}/members", headers=_headers(attacker)).status_code == 404
    assert client.get(f"/api/organizations/{org.id}/members", headers=_headers(member)).status_code == 200
    assert client.post(
        f"/api/organizations/{org.id}/teams", headers=_headers(member), json={"name": "Unauthorized"}
    ).status_code == 404

    org.status = "Suspended"
    db.session.commit()
    assert client.get(f"/api/organizations/{org.id}/members", headers=_headers(member)).status_code == 404
    assert client.post(
        f"/api/organizations/{org.id}/invite", headers=_headers(attacker), json={"email": "victim@example.com"}
    ).status_code == 404


def test_master_can_manage_members_but_subaccount_cannot_escalate(client, db):
    owner = _user(db, "master@example.com")
    subaccount = _user(db, "subaccount@example.com")
    other = _user(db, "other-subaccount@example.com")
    org = Organization(name="Managed Org", owner_id=owner.id)
    db.session.add(org)
    db.session.flush()
    viewer = OrganizationRole(org_id=org.id, name="Viewer", permissions="[]")
    manager = OrganizationRole(org_id=org.id, name="Manager", permissions='["manage_users"]')
    db.session.add_all([viewer, manager])
    db.session.flush()
    owner_member = OrganizationMember(org_id=org.id, user_id=owner.id, role_id=manager.id)
    db.session.add(owner_member)
    db.session.commit()

    added = client.post(
        f"/api/organizations/{org.id}/members", headers=_headers(owner),
        json={"email": subaccount.email, "role_id": viewer.id},
    )
    assert added.status_code == 201
    member_id = added.get_json()["member"]["id"]
    assert client.patch(
        f"/api/organizations/{org.id}/members/{member_id}", headers=_headers(subaccount),
        json={"role_id": manager.id},
    ).status_code == 404
    assert client.post(
        f"/api/organizations/{org.id}/members", headers=_headers(subaccount),
        json={"email": other.email, "role_id": manager.id},
    ).status_code == 404
    assert client.get(f"/api/organizations/{org.id}/usage", headers=_headers(subaccount)).status_code == 404

    updated = client.patch(
        f"/api/organizations/{org.id}/members/{member_id}", headers=_headers(owner),
        json={"status": "Suspended", "role_id": manager.id},
    )
    assert updated.status_code == 200
    assert updated.get_json()["member"]["status"] == "Suspended"
    assert client.delete(
        f"/api/organizations/{org.id}/members/{owner_member.id}", headers=_headers(owner)
    ).status_code == 409
    assert client.delete(
        f"/api/organizations/{org.id}/members/{member_id}", headers=_headers(owner)
    ).status_code == 200


def test_delegated_manager_cannot_grant_stronger_role(client, db):
    owner = _user(db, "role-owner@example.com")
    manager_user = _user(db, "role-manager@example.com")
    target = _user(db, "role-target@example.com")
    org = Organization(name="Role Boundaries", owner_id=owner.id)
    db.session.add(org)
    db.session.flush()
    manager = OrganizationRole(org_id=org.id, name="Manager", permissions='["manage_users"]')
    administrator = OrganizationRole(org_id=org.id, name="Administrator", permissions='["all"]')
    db.session.add_all([manager, administrator])
    db.session.flush()
    db.session.add(OrganizationMember(org_id=org.id, user_id=manager_user.id, role_id=manager.id))
    db.session.commit()
    response = client.post(
        f"/api/organizations/{org.id}/members", headers=_headers(manager_user),
        json={"email": target.email, "role_id": administrator.id},
    )
    assert response.status_code == 403


def test_tenant_provider_and_billing_policy_is_owner_scoped_and_enforced(client, db):
    owner = _user(db, "policy-owner@example.com")
    member = _user(db, "policy-member@example.com")
    outsider = _user(db, "policy-outsider@example.com")
    org = Organization(name="Policy Org", owner_id=owner.id)
    db.session.add(org)
    db.session.flush()
    role = OrganizationRole(org_id=org.id, name="Viewer", permissions="[]")
    db.session.add(role)
    db.session.flush()
    db.session.add(OrganizationMember(org_id=org.id, user_id=member.id, role_id=role.id))
    db.session.commit()

    updated = client.patch(
        f"/api/organizations/{org.id}/policy", headers=_headers(owner),
        json={"allowed_providers": ["openai"], "billing_enabled": False},
    )
    assert updated.status_code == 200
    assert updated.get_json()["policy"]["allowed_providers"] == ["openai"]
    assert client.get(f"/api/organizations/{org.id}/policy", headers=_headers(member)).status_code == 200
    assert client.patch(
        f"/api/organizations/{org.id}/policy", headers=_headers(member),
        json={"allowed_providers": ["gemini"]},
    ).status_code == 403
    assert client.get(f"/api/organizations/{org.id}/policy", headers=_headers(outsider)).status_code == 404
    billing = client.get("/api/billing/config", headers=_headers(member))
    assert billing.status_code == 200
    assert billing.get_json()["tenant_billing_enabled"] is False
    assert client.post(
        "/api/billing/checkout", headers=_headers(member), json={"plan": "Pro"}
    ).status_code == 403


def test_organization_project_sharing_enforces_tenant_and_role_permissions(client, db):
    owner = _user(db, "project-master@example.com")
    viewer_user = _user(db, "project-viewer@example.com")
    editor_user = _user(db, "project-editor@example.com")
    attacker = _user(db, "project-outsider@example.com")
    org = Organization(name="Project Org", owner_id=owner.id)
    workspace = Workspace(user_id=owner.id, name="Owner Workspace")
    db.session.add_all([org, workspace])
    db.session.flush()
    project = Project(workspace_id=workspace.id, name="Shared Project")
    viewer = OrganizationRole(org_id=org.id, name="Viewer", permissions="[]")
    editor = OrganizationRole(org_id=org.id, name="Editor", permissions='["manage_projects"]')
    db.session.add_all([project, viewer, editor])
    db.session.flush()
    db.session.add_all([
        OrganizationMember(org_id=org.id, user_id=owner.id, role_id=editor.id),
        OrganizationMember(org_id=org.id, user_id=viewer_user.id, role_id=viewer.id),
        OrganizationMember(org_id=org.id, user_id=editor_user.id, role_id=editor.id),
    ])
    db.session.commit()

    share = client.post(
        f"/api/organizations/{org.id}/projects/{project.id}", headers=_headers(owner),
        json={"access_level": "edit"},
    )
    assert share.status_code == 200
    assert client.get(f"/api/project/{project.id}", headers=_headers(viewer_user)).status_code == 200
    assert client.put(
        f"/api/project/{project.id}", headers=_headers(viewer_user), json={"name": "Escalated"}
    ).status_code == 404
    assert client.put(
        f"/api/project/{project.id}", headers=_headers(editor_user), json={"name": "Authorized edit"}
    ).status_code == 200
    assert client.get(f"/api/project/{project.id}", headers=_headers(attacker)).status_code == 404
    assert client.get(f"/api/organizations/{org.id}/projects", headers=_headers(attacker)).status_code == 404
    assert client.delete(
        f"/api/organizations/{org.id}/projects/{project.id}", headers=_headers(viewer_user)
    ).status_code == 404


def test_saas_routes_no_longer_share_anonymous_identity(client):
    assert client.get("/api/saas/apikeys").status_code == 401
    assert client.post("/api/saas/apikeys", json={"key_name": "anonymous"}).status_code == 401


def test_user_data_and_generation_routes_reject_anonymous_requests(client):
    assert client.post("/api/chat", json={"message": "anonymous"}).status_code == 401
    assert client.post("/api/chat/stream", json={"message": "anonymous"}).status_code == 401
    assert client.post("/api/chat/stop", json={"generation_id": "unknown"}).status_code == 401
    assert client.get("/api/history").status_code == 401
    assert client.get("/api/memory/list").status_code == 401
    assert client.post(
        "/api/feedback/correction",
        json={"question": "q", "bot_answer": "a", "is_correct": True},
    ).status_code == 401


def test_normal_user_cannot_execute_or_load_host_plugins(client, db):
    user = _user(db, "plugin-client@example.com")
    headers = _headers(user)
    assert client.post(
        "/api/plugins/registry/load", headers=headers, json={"directory": "C:\\"}
    ).status_code == 403
    assert client.post(
        "/api/plugins/registry/anything/execute", headers=headers, json={}
    ).status_code == 403
