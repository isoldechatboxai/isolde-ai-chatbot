# app/routes/collaboration_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.collaboration_model import Organization, OrganizationRole, OrganizationMember, Team, Invitation

collaboration_bp = Blueprint("collaboration_bp", __name__)

# --- ORGANIZATION APIs ---
@collaboration_bp.route("/organizations", methods=["GET"])
@jwt_required(optional=True)
def get_organizations():
    try:
        user_id = get_jwt_identity() or 1 # Fallback for local testing
        # Get Orgs where user is owner OR a member
        owned_orgs = Organization.query.filter_by(owner_id=user_id).all()
        member_org_ids = [m.org_id for m in OrganizationMember.query.filter_by(user_id=user_id).all()]
        member_orgs = Organization.query.filter(Organization.id.in_(member_org_ids)).all()
        
        all_orgs = {org.id: org for org in owned_orgs + member_orgs}.values()
        
        return jsonify({"organizations": [o.to_dict() for o in all_orgs]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@collaboration_bp.route("/organizations", methods=["POST"])
@jwt_required(optional=True)
def create_organization():
    try:
        user_id = get_jwt_identity() or 1
        data = request.get_json() or {}
        
        org = Organization(
            name=data.get("name", "New Enterprise Org"),
            description=data.get("description", ""),
            owner_id=user_id
        )
        db.session.add(org)
        db.session.flush() # Get org ID
        
        # Create default Admin Role
        admin_role = OrganizationRole(org_id=org.id, name="Admin", permissions='["all"]')
        db.session.add(admin_role)
        db.session.flush()

        # Add creator as Member with Admin Role
        member = OrganizationMember(org_id=org.id, user_id=user_id, role_id=admin_role.id)
        db.session.add(member)
        
        db.session.commit()
        return jsonify({"message": "Organization created successfully", "organization": org.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- TEAM APIs ---
@collaboration_bp.route("/organizations/<int:org_id>/teams", methods=["GET"])
@jwt_required(optional=True)
def get_teams(org_id):
    try:
        teams = Team.query.filter_by(org_id=org_id).order_by(Team.created_at.desc()).all()
        return jsonify({"teams": [t.to_dict() for t in teams]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@collaboration_bp.route("/organizations/<int:org_id>/teams", methods=["POST"])
@jwt_required(optional=True)
def create_team(org_id):
    try:
        data = request.get_json() or {}
        team = Team(
            org_id=org_id,
            name=data.get("name", "New Team"),
            description=data.get("description", "")
        )
        db.session.add(team)
        db.session.commit()
        return jsonify({"message": "Team created", "team": team.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- MEMBER & INVITATION APIs ---
@collaboration_bp.route("/organizations/<int:org_id>/members", methods=["GET"])
@jwt_required(optional=True)
def get_members(org_id):
    try:
        members = OrganizationMember.query.filter_by(org_id=org_id).all()
        return jsonify({"members": [m.to_dict() for m in members]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@collaboration_bp.route("/organizations/<int:org_id>/invite", methods=["POST"])
@jwt_required(optional=True)
def invite_user(org_id):
    try:
        data = request.get_json() or {}
        email = data.get("email")
        if not email:
            return jsonify({"error": "Email is required"}), 400

        invite = Invitation(
            org_id=org_id,
            email=email,
            role_id=data.get("role_id")
        )
        db.session.add(invite)
        db.session.commit()
        
        # Here we would send an actual email using a background task
        return jsonify({"message": f"Invitation sent to {email}", "invitation": invite.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500