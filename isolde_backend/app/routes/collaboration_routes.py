import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.collaboration_model import Invitation, Organization, OrganizationMember, OrganizationRole, Team, OrganizationProject, OrganizationPolicy
from app.services.organization_policy_service import SUPPORTED_PROVIDERS
from app.models.user import User
from app.models.workspace_model import Project, Workspace
from app.utils.validators import is_valid_email

collaboration_bp = Blueprint("collaboration_bp", __name__)


def _user_id():
    return str(get_jwt_identity())


def _organization_for_member(org_id, user_id):
    return Organization.query.filter(
        Organization.id == org_id,
        Organization.status == "Active",
        db.or_(
            Organization.owner_id == user_id,
            Organization.id.in_(db.session.query(OrganizationMember.org_id).filter_by(user_id=user_id, status="Active")),
        ),
    ).first()


def _organization_for_admin(org_id, user_id):
    org = Organization.query.filter_by(id=org_id, status="Active").first()
    if not org:
        return None
    if org.owner_id == user_id:
        return org
    member = OrganizationMember.query.filter_by(org_id=org_id, user_id=user_id, status="Active").first()
    role = db.session.get(OrganizationRole, member.role_id) if member else None
    try:
        permissions = json.loads(role.permissions or "[]") if role else []
    except (TypeError, ValueError):
        permissions = []
    return org if "all" in permissions or "manage_users" in permissions else None


def _organization_for_owner(org_id, user_id):
    return Organization.query.filter_by(id=org_id, owner_id=user_id, status="Active").first()


def _permissions_for_member(member):
    role = db.session.get(OrganizationRole, member.role_id) if member and member.role_id else None
    try:
        return set(json.loads(role.permissions or "[]")) if role else set()
    except (TypeError, ValueError):
        return set()


def _member_payload(member):
    user = db.session.get(User, member.user_id)
    role = db.session.get(OrganizationRole, member.role_id) if member.role_id else None
    payload = member.to_dict()
    payload.update({
        "name": user.name if user else None,
        "email": user.email if user else None,
        "role": role.to_dict() if role else None,
    })
    return payload


@collaboration_bp.route("/organizations", methods=["GET"])
@jwt_required()
def get_organizations():
    user_id = _user_id()
    owned = Organization.query.filter_by(owner_id=user_id).all()
    member_ids = db.session.query(OrganizationMember.org_id).filter_by(user_id=user_id, status="Active")
    member = Organization.query.filter(Organization.id.in_(member_ids)).all()
    organizations = {item.id: item for item in owned + member}
    return jsonify({"organizations": [item.to_dict() for item in organizations.values()]}), 200


@collaboration_bp.route("/organizations", methods=["POST"])
@jwt_required()
def create_organization():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Organization name is required."}), 400
    user_id = _user_id()
    org = Organization(name=name[:255], description=str(data.get("description") or "")[:2000], owner_id=user_id)
    db.session.add(org)
    db.session.flush()
    role = OrganizationRole(org_id=org.id, name="Admin", permissions='["all"]')
    db.session.add(role)
    db.session.flush()
    db.session.add(OrganizationMember(org_id=org.id, user_id=user_id, role_id=role.id))
    db.session.commit()
    return jsonify({"message": "Organization created successfully", "organization": org.to_dict()}), 201


@collaboration_bp.route("/organizations/<int:org_id>/teams", methods=["GET"])
@jwt_required()
def get_teams(org_id):
    if not _organization_for_member(org_id, _user_id()):
        return jsonify({"error": "Organization not found."}), 404
    teams = Team.query.filter_by(org_id=org_id).order_by(Team.created_at.desc()).all()
    return jsonify({"teams": [item.to_dict() for item in teams]}), 200


@collaboration_bp.route("/organizations/<int:org_id>/teams", methods=["POST"])
@jwt_required()
def create_team(org_id):
    if not _organization_for_admin(org_id, _user_id()):
        return jsonify({"error": "Organization not found."}), 404
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Team name is required."}), 400
    team = Team(org_id=org_id, name=name[:100], description=str(data.get("description") or "")[:2000])
    db.session.add(team)
    db.session.commit()
    return jsonify({"message": "Team created", "team": team.to_dict()}), 201


@collaboration_bp.route("/organizations/<int:org_id>/members", methods=["GET"])
@jwt_required()
def get_members(org_id):
    if not _organization_for_member(org_id, _user_id()):
        return jsonify({"error": "Organization not found."}), 404
    members = OrganizationMember.query.filter_by(org_id=org_id).all()
    return jsonify({"members": [_member_payload(item) for item in members]}), 200


@collaboration_bp.route("/organizations/<int:org_id>/roles", methods=["GET"])
@jwt_required()
def get_roles(org_id):
    if not _organization_for_member(org_id, _user_id()):
        return jsonify({"error": "Organization not found."}), 404
    roles = OrganizationRole.query.filter_by(org_id=org_id).all()
    return jsonify({"roles": [role.to_dict() for role in roles]}), 200


@collaboration_bp.route("/organizations/<int:org_id>/members", methods=["POST"])
@jwt_required()
def add_member(org_id):
    actor_id = _user_id()
    org = _organization_for_admin(org_id, actor_id)
    if not org:
        return jsonify({"error": "Organization not found."}), 404
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email, status="Active").first()
    role = OrganizationRole.query.filter_by(id=data.get("role_id"), org_id=org_id).first()
    if not user:
        return jsonify({"error": "An active registered user with that email is required."}), 404
    if not role:
        return jsonify({"error": "Role not found."}), 404
    if org.owner_id != actor_id:
        actor = OrganizationMember.query.filter_by(org_id=org_id, user_id=actor_id, status="Active").first()
        actor_permissions = _permissions_for_member(actor)
        try:
            granted_permissions = set(json.loads(role.permissions or "[]"))
        except (TypeError, ValueError):
            granted_permissions = set()
        if not granted_permissions.issubset(actor_permissions):
            return jsonify({"error": "You cannot grant permissions you do not have."}), 403
    member = OrganizationMember.query.filter_by(org_id=org_id, user_id=user.id).first()
    if member:
        member.role_id = role.id
        member.status = "Active"
    else:
        member = OrganizationMember(org_id=org_id, user_id=user.id, role_id=role.id, status="Active")
        db.session.add(member)
    db.session.commit()
    return jsonify({"message": "Member added.", "member": _member_payload(member)}), 201


@collaboration_bp.route("/organizations/<int:org_id>/members/<int:member_id>", methods=["PATCH", "DELETE"])
@jwt_required()
def manage_member(org_id, member_id):
    org = _organization_for_admin(org_id, _user_id())
    if not org:
        return jsonify({"error": "Organization not found."}), 404
    member = OrganizationMember.query.filter_by(id=member_id, org_id=org_id).first()
    if not member:
        return jsonify({"error": "Member not found."}), 404
    if member.user_id == org.owner_id:
        return jsonify({"error": "Organization ownership cannot be changed through member management."}), 409
    actor_id = _user_id()
    actor = OrganizationMember.query.filter_by(org_id=org_id, user_id=actor_id, status="Active").first()
    actor_permissions = {"all"} if org.owner_id == actor_id else _permissions_for_member(actor)
    target_permissions = _permissions_for_member(member)
    if "all" not in actor_permissions and not target_permissions.issubset(actor_permissions):
        return jsonify({"error": "You cannot manage a member with stronger permissions."}), 403
    if request.method == "DELETE":
        db.session.delete(member)
        db.session.commit()
        return jsonify({"message": "Member removed."}), 200
    data = request.get_json(silent=True) or {}
    if "status" in data:
        if data["status"] not in {"Active", "Suspended"}:
            return jsonify({"error": "Status must be Active or Suspended."}), 400
        member.status = data["status"]
    if "role_id" in data:
        role = OrganizationRole.query.filter_by(id=data["role_id"], org_id=org_id).first()
        if not role:
            return jsonify({"error": "Role not found."}), 404
        try:
            new_permissions = set(json.loads(role.permissions or "[]"))
        except (TypeError, ValueError):
            new_permissions = set()
        if "all" not in actor_permissions and not new_permissions.issubset(actor_permissions):
            return jsonify({"error": "You cannot grant permissions you do not have."}), 403
        member.role_id = role.id
    db.session.commit()
    return jsonify({"message": "Member updated.", "member": _member_payload(member)}), 200


@collaboration_bp.route("/organizations/<int:org_id>/policy", methods=["GET", "PATCH"])
@jwt_required()
def organization_policy(org_id):
    user_id = _user_id()
    org = _organization_for_member(org_id, user_id)
    if not org:
        return jsonify({"error": "Organization not found."}), 404
    policy = OrganizationPolicy.query.filter_by(org_id=org_id).first()
    if request.method == "GET":
        return jsonify({"policy": policy.to_dict() if policy else {
            "org_id": org_id, "allowed_providers": [], "billing_enabled": True, "updated_at": None,
        }}), 200
    if org.owner_id != user_id:
        db.session.rollback()
        return jsonify({"error": "Only the organization owner can update tenant policy."}), 403
    data = request.get_json(silent=True) or {}
    if not policy:
        policy = OrganizationPolicy(org_id=org_id)
        db.session.add(policy)
    if "allowed_providers" in data:
        providers = data["allowed_providers"]
        if not isinstance(providers, list) or not providers:
            return jsonify({"error": "At least one allowed provider is required."}), 400
        normalized = sorted({str(item).strip().lower() for item in providers})
        if not set(normalized).issubset(SUPPORTED_PROVIDERS):
            return jsonify({"error": "Unsupported provider in policy."}), 400
        policy.allowed_providers = json.dumps(normalized)
    if "billing_enabled" in data:
        if not isinstance(data["billing_enabled"], bool):
            return jsonify({"error": "billing_enabled must be a boolean."}), 400
        policy.billing_enabled = data["billing_enabled"]
    db.session.commit()
    return jsonify({"message": "Tenant policy updated.", "policy": policy.to_dict()}), 200


@collaboration_bp.route("/organizations/<int:org_id>/usage", methods=["GET"])
@jwt_required()
def organization_usage(org_id):
    org = _organization_for_owner(org_id, _user_id())
    if not org:
        return jsonify({"error": "Organization not found."}), 404
    member_ids = {row[0] for row in db.session.query(OrganizationMember.user_id).filter_by(org_id=org_id, status="Active").all()}
    member_ids.add(org.owner_id)
    users = User.query.filter(User.id.in_(member_ids)).all() if member_ids else []
    return jsonify({
        "usage": "Usage unavailable",
        "members": [{"user_id": user.id, "name": user.name, "account_tokens_used": user.tokens_used} for user in users],
        "tokens_used": None,
        "account_tokens_used": sum(user.tokens_used or 0 for user in users),
    }), 200


@collaboration_bp.route("/organizations/<int:org_id>/projects", methods=["GET"])
@jwt_required()
def organization_projects(org_id):
    if not _organization_for_member(org_id, _user_id()):
        return jsonify({"error": "Organization not found."}), 404
    shares = OrganizationProject.query.filter_by(org_id=org_id).all()
    projects = []
    for share in shares:
        project = db.session.get(Project, share.project_id)
        if project:
            projects.append({**project.to_dict(), "shared_access": share.access_level})
    return jsonify({"projects": projects}), 200


@collaboration_bp.route("/organizations/<int:org_id>/projects/<int:project_id>", methods=["POST", "DELETE"])
@jwt_required()
def manage_organization_project(org_id, project_id):
    org = _organization_for_owner(org_id, _user_id())
    if not org:
        return jsonify({"error": "Organization not found."}), 404
    project = Project.query.join(Workspace).filter(Project.id == project_id, Workspace.user_id == org.owner_id).first()
    if not project:
        return jsonify({"error": "Project not found."}), 404
    share = OrganizationProject.query.filter_by(project_id=project_id).first()
    if request.method == "DELETE":
        if not share or share.org_id != org_id:
            return jsonify({"error": "Shared project not found."}), 404
        db.session.delete(share)
        db.session.commit()
        return jsonify({"message": "Project sharing removed."}), 200
    access_level = str((request.get_json(silent=True) or {}).get("access_level") or "view")
    if access_level not in {"view", "edit"}:
        return jsonify({"error": "Access level must be view or edit."}), 400
    if share and share.org_id != org_id:
        return jsonify({"error": "Project is already shared with another organization."}), 409
    if not share:
        share = OrganizationProject(org_id=org_id, project_id=project_id, shared_by=_user_id())
        db.session.add(share)
    share.access_level = access_level
    db.session.commit()
    return jsonify({"message": "Project shared.", "share": share.to_dict()}), 200


@collaboration_bp.route("/organizations/<int:org_id>/invite", methods=["POST"])
@jwt_required()
def invite_user(org_id):
    if not _organization_for_admin(org_id, _user_id()):
        return jsonify({"error": "Organization not found."}), 404
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    if not is_valid_email(email):
        return jsonify({"error": "Valid email is required."}), 400
    role_id = data.get("role_id")
    if role_id and not OrganizationRole.query.filter_by(id=role_id, org_id=org_id).first():
        return jsonify({"error": "Role not found."}), 404
    invite = Invitation(org_id=org_id, email=email, role_id=role_id)
    db.session.add(invite)
    db.session.commit()
    return jsonify({
        "message": "Invitation created. Delivery requires configured email service.",
        "invitation": invite.to_dict(),
    }), 201
