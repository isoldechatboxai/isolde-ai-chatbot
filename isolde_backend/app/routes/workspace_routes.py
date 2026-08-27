# app/routes/workspace_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.workspace_model import Workspace, Project
from app.models.collaboration_model import OrganizationMember, OrganizationProject, OrganizationRole
import json

workspace_bp = Blueprint("workspace_bp", __name__)


def get_current_user_id():
    """Safely get the authenticated user ID. Returns None if not authenticated."""
    try:
        return get_jwt_identity()
    except Exception:
        return None


def _shared_project(project_id, user_id, require_edit=False):
    share = OrganizationProject.query.join(
        OrganizationMember, OrganizationMember.org_id == OrganizationProject.org_id
    ).filter(
        OrganizationProject.project_id == project_id,
        OrganizationMember.user_id == str(user_id),
        OrganizationMember.status == "Active",
    ).first()
    if not share:
        return None
    if require_edit:
        member = OrganizationMember.query.filter_by(org_id=share.org_id, user_id=str(user_id), status="Active").first()
        role = db.session.get(OrganizationRole, member.role_id) if member else None
        try:
            permissions = json.loads(role.permissions or "[]") if role else []
        except (TypeError, ValueError):
            permissions = []
        if share.access_level != "edit" or not ({"all", "manage_projects"} & set(permissions)):
            return None
    return db.session.get(Project, project_id)


# ---------------------------------------------------------------------------
# WORKSPACE CRUD
# ---------------------------------------------------------------------------

@workspace_bp.route("/workspace/list", methods=["GET"])
@jwt_required()
def list_workspaces():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workspaces = (
            Workspace.query.filter_by(user_id=user_id)
            .order_by(Workspace.created_at.desc())
            .all()
        )
        return jsonify({"workspaces": [w.to_dict() for w in workspaces]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch workspaces"}), 500


@workspace_bp.route("/workspace/create", methods=["POST"])
@jwt_required()
def create_workspace():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Workspace name is required"}), 400

        workspace = Workspace(
            user_id=user_id,
            name=name,
            description=(data.get("description") or "").strip() or None,
        )
        db.session.add(workspace)
        db.session.commit()
        return jsonify({"message": "Workspace created", "workspace": workspace.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create workspace"}), 500


@workspace_bp.route("/workspace/<int:workspace_id>", methods=["GET"])
@jwt_required()
def get_workspace(workspace_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workspace = Workspace.query.filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        return jsonify({"workspace": workspace.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch workspace"}), 500


@workspace_bp.route("/workspace/<int:workspace_id>", methods=["PUT"])
@jwt_required()
def update_workspace(workspace_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workspace = Workspace.query.filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        if "name" in data and data["name"].strip():
            workspace.name = data["name"].strip()
        if "description" in data:
            workspace.description = (data["description"] or "").strip() or None
        if "is_active" in data:
            workspace.is_active = bool(data["is_active"])

        db.session.commit()
        return jsonify({"message": "Workspace updated", "workspace": workspace.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update workspace"}), 500


@workspace_bp.route("/workspace/<int:workspace_id>", methods=["DELETE"])
@jwt_required()
def delete_workspace(workspace_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workspace = Workspace.query.filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        db.session.delete(workspace)  # cascades to projects/agents/documents
        db.session.commit()
        return jsonify({"message": "Workspace deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete workspace"}), 500


# ---------------------------------------------------------------------------
# PROJECT CRUD (scoped to a workspace)
# ---------------------------------------------------------------------------

@workspace_bp.route("/workspace/<int:workspace_id>/projects", methods=["GET"])
@jwt_required()
def list_projects(workspace_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Verify workspace ownership
        workspace = Workspace.query.filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        projects = (
            Project.query.filter_by(workspace_id=workspace_id)
            .order_by(Project.created_at.desc())
            .all()
        )
        return jsonify({"projects": [p.to_dict() for p in projects]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch projects"}), 500


@workspace_bp.route("/workspace/<int:workspace_id>/projects", methods=["POST"])
@jwt_required()
def create_project(workspace_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Verify workspace ownership
        workspace = Workspace.query.filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Project name is required"}), 400

        project = Project(
            workspace_id=workspace_id,
            name=name,
            description=(data.get("description") or "").strip() or None,
            status=(data.get("status") or "Active").strip(),
        )
        db.session.add(project)
        db.session.commit()
        return jsonify({"message": "Project created", "project": project.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create project"}), 500


@workspace_bp.route("/project/<int:project_id>", methods=["GET"])
@jwt_required()
def get_project(project_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        project = Project.query.join(Workspace).filter(
            Project.id == project_id,
            Workspace.user_id == user_id
        ).first() or _shared_project(project_id, user_id)
        if not project:
            return jsonify({"error": "Project not found"}), 404

        return jsonify({"project": project.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch project"}), 500


@workspace_bp.route("/project/<int:project_id>", methods=["PUT"])
@jwt_required()
def update_project(project_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Verify ownership through workspace relationship
        project = Project.query.join(Workspace).filter(
            Project.id == project_id,
            Workspace.user_id == user_id
        ).first() or _shared_project(project_id, user_id, require_edit=True)
        if not project:
            return jsonify({"error": "Project not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        if "name" in data and data["name"].strip():
            project.name = data["name"].strip()
        if "description" in data:
            project.description = (data["description"] or "").strip() or None
        if "status" in data:
            project.status = data["status"].strip()

        db.session.commit()
        return jsonify({"message": "Project updated", "project": project.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update project"}), 500


@workspace_bp.route("/project/<int:project_id>", methods=["DELETE"])
@jwt_required()
def delete_project(project_id: int):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Verify ownership through workspace relationship
        project = Project.query.join(Workspace).filter(
            Project.id == project_id,
            Workspace.user_id == user_id
        ).first()
        if not project:
            return jsonify({"error": "Project not found"}), 404

        db.session.delete(project)
        db.session.commit()
        return jsonify({"message": "Project deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete project"}), 500
