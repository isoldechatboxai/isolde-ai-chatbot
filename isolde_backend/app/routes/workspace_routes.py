# app/routes/workspace_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.workspace_model import Workspace, Project

workspace_bp = Blueprint("workspace_bp", __name__)


# ---------------------------------------------------------------------------
# WORKSPACE CRUD
# ---------------------------------------------------------------------------

@workspace_bp.route("/workspace/list", methods=["GET"])
@jwt_required(optional=True)
def list_workspaces():
    try:
        user_id = get_jwt_identity() or "guest_user"
        workspaces = (
            Workspace.query.filter_by(user_id=user_id)
            .order_by(Workspace.created_at.desc())
            .all()
        )
        return jsonify({"workspaces": [w.to_dict() for w in workspaces]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch workspaces", "details": str(e)}), 500


@workspace_bp.route("/workspace/create", methods=["POST"])
@jwt_required(optional=True)
def create_workspace():
    try:
        user_id = get_jwt_identity() or "guest_user"
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"error": "Workspace name is required"}), 400

        workspace = Workspace(
            user_id=user_id,
            name=name,
            description=data.get("description", "").strip() or None,
        )
        db.session.add(workspace)
        db.session.commit()
        return jsonify({"message": "Workspace created", "workspace": workspace.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create workspace", "details": str(e)}), 500


@workspace_bp.route("/workspace/<int:workspace_id>", methods=["PUT"])
@jwt_required(optional=True)
def update_workspace(workspace_id: int):
    try:
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        data = request.get_json() or {}
        if "name" in data and data["name"].strip():
            workspace.name = data["name"].strip()
        if "description" in data:
            workspace.description = data["description"].strip() or None
        if "is_active" in data:
            workspace.is_active = bool(data["is_active"])

        db.session.commit()
        return jsonify({"message": "Workspace updated", "workspace": workspace.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update workspace", "details": str(e)}), 500


@workspace_bp.route("/workspace/<int:workspace_id>", methods=["DELETE"])
@jwt_required(optional=True)
def delete_workspace(workspace_id: int):
    try:
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        db.session.delete(workspace)  # cascades to projects/agents/documents
        db.session.commit()
        return jsonify({"message": "Workspace deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete workspace", "details": str(e)}), 500


# ---------------------------------------------------------------------------
# PROJECT CRUD (scoped to a workspace)
# ---------------------------------------------------------------------------

@workspace_bp.route("/workspace/<int:workspace_id>/projects", methods=["GET"])
@jwt_required(optional=True)
def list_projects(workspace_id: int):
    try:
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        projects = (
            Project.query.filter_by(workspace_id=workspace_id)
            .order_by(Project.created_at.desc())
            .all()
        )
        return jsonify({"projects": [p.to_dict() for p in projects]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch projects", "details": str(e)}), 500


@workspace_bp.route("/workspace/<int:workspace_id>/projects", methods=["POST"])
@jwt_required(optional=True)
def create_project(workspace_id: int):
    try:
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Project name is required"}), 400

        project = Project(
            workspace_id=workspace_id,
            name=name,
            description=data.get("description", "").strip() or None,
            status=data.get("status", "Active"),
        )
        db.session.add(project)
        db.session.commit()
        return jsonify({"message": "Project created", "project": project.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create project", "details": str(e)}), 500


@workspace_bp.route("/project/<int:project_id>", methods=["PUT"])
@jwt_required(optional=True)
def update_project(project_id: int):
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({"error": "Project not found"}), 404

        data = request.get_json() or {}
        if "name" in data and data["name"].strip():
            project.name = data["name"].strip()
        if "description" in data:
            project.description = data["description"].strip() or None
        if "status" in data:
            project.status = data["status"]

        db.session.commit()
        return jsonify({"message": "Project updated", "project": project.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update project", "details": str(e)}), 500


@workspace_bp.route("/project/<int:project_id>", methods=["DELETE"])
@jwt_required(optional=True)
def delete_project(project_id: int):
    try:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({"error": "Project not found"}), 404

        db.session.delete(project)
        db.session.commit()
        return jsonify({"message": "Project deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete project", "details": str(e)}), 500