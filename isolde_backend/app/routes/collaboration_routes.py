import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.collaboration_model import Invitation, Organization, OrganizationMember, OrganizationRole, Team
from app.utils.validators import is_valid_email

collaboration_bp = Blueprint("collaboration_bp", __name__)


def _user_id():
    return str(get_jwt_identity())


def _organization_for_member(org_id, user_id):
    return Organization.query.filter(
        Organization.id == org_id,
        db.or_(
            Organization.owner_id == user_id,
            Organization.id.in_(db.session.query(OrganizationMember.org_id).filter_by(user_id=user_id, status="Active")),
        ),
    ).first()


def _organization_for_admin(org_id, user_id):
    org = Organization.query.filter_by(id=org_id).first()
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
    return jsonify({"members": [item.to_dict() for item in members]}), 200


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
