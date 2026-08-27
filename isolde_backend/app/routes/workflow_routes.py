# app/routes/workflow_routes.py
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.workflow_model import Workflow, WorkflowExecution, Webhook
from app.models.workspace_model import Workspace

workflow_bp = Blueprint("workflow_bp", __name__)


def get_current_user_id():
    """Safely get the authenticated user ID. Returns None if not authenticated."""
    try:
        return get_jwt_identity()
    except Exception:
        return None


def verify_workflow_ownership(workflow_id, user_id):
    """Verify that a workflow belongs to the user's workspace."""
    workflow = Workflow.query.join(Workspace).filter(
        Workflow.id == workflow_id,
        Workspace.user_id == user_id
    ).first()
    return workflow


@workflow_bp.route("/workflows", methods=["GET"])
@jwt_required()
def get_workflows():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get all workspaces for this user
        user_workspaces = Workspace.query.filter_by(user_id=user_id).all()
        workspace_ids = [w.id for w in user_workspaces]
        
        # Filter workflows by user's workspaces
        if workspace_ids:
            workflows = Workflow.query.filter(
                Workflow.workspace_id.in_(workspace_ids)
            ).order_by(Workflow.created_at.desc()).all()
        else:
            workflows = []
        
        return jsonify({"workflows": [w.to_dict() for w in workflows]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch workflows"}), 500


@workflow_bp.route("/workflows", methods=["POST"])
@jwt_required()
def create_workflow():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Workflow name is required"}), 400
        
        workspace_id = data.get("workspace_id")
        if not workspace_id:
            return jsonify({"error": "Workspace ID is required"}), 400
        
        # Verify workspace ownership
        workspace = Workspace.query.filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404
        trigger_type = str(data.get("trigger_type") or "Manual").strip()
        if trigger_type != "Manual":
            return jsonify({
                "status": "NOT_SUPPORTED",
                "error": "Only manual workflow definitions are supported; scheduled and webhook execution are not configured."
            }), 422
        
        workflow = Workflow(
            name=name,
            description=(data.get("description") or "").strip() or None,
            trigger_type=trigger_type,
            workspace_id=workspace_id
        )
        db.session.add(workflow)
        db.session.commit()
        return jsonify({"message": "Workflow created", "workflow": workflow.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create workflow"}), 500


@workflow_bp.route("/workflows/<int:workflow_id>", methods=["GET"])
@jwt_required()
def get_workflow(workflow_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workflow = verify_workflow_ownership(workflow_id, user_id)
        if not workflow:
            return jsonify({"error": "Workflow not found"}), 404
        
        return jsonify({"workflow": workflow.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch workflow"}), 500


@workflow_bp.route("/workflows/<int:workflow_id>", methods=["PUT"])
@jwt_required()
def update_workflow(workflow_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workflow = verify_workflow_ownership(workflow_id, user_id)
        if not workflow:
            return jsonify({"error": "Workflow not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        if "name" in data and data["name"].strip():
            workflow.name = data["name"].strip()
        if "description" in data:
            workflow.description = (data["description"] or "").strip() or None
        if "trigger_type" in data:
            trigger_type = str(data["trigger_type"] or "").strip()
            if trigger_type != "Manual":
                return jsonify({
                    "status": "NOT_SUPPORTED",
                    "error": "Only manual workflow definitions are supported."
                }), 422
            workflow.trigger_type = trigger_type
        if "is_active" in data:
            workflow.is_active = bool(data["is_active"])
        
        db.session.commit()
        return jsonify({"message": "Workflow updated", "workflow": workflow.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update workflow"}), 500


@workflow_bp.route("/workflows/<int:workflow_id>", methods=["DELETE"])
@jwt_required()
def delete_workflow(workflow_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workflow = verify_workflow_ownership(workflow_id, user_id)
        if not workflow:
            return jsonify({"error": "Workflow not found"}), 404
        
        db.session.delete(workflow)
        db.session.commit()
        return jsonify({"message": "Workflow deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete workflow"}), 500


@workflow_bp.route("/workflows/<int:workflow_id>/execute", methods=["POST"])
@jwt_required()
def execute_workflow(workflow_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workflow = verify_workflow_ownership(workflow_id, user_id)
        if not workflow:
            return jsonify({"error": "Workflow not found"}), 404
        
        if not workflow.is_active:
            return jsonify({"error": "Workflow is not active"}), 400
        
        return jsonify({
            "error": "Workflow execution is not configured."
        }), 501
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to execute workflow"}), 500


@workflow_bp.route("/workflows/<int:workflow_id>/executions", methods=["GET"])
@jwt_required()
def get_workflow_executions(workflow_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workflow = verify_workflow_ownership(workflow_id, user_id)
        if not workflow:
            return jsonify({"error": "Workflow not found"}), 404
        
        executions = WorkflowExecution.query.filter_by(
            workflow_id=workflow_id
        ).order_by(WorkflowExecution.started_at.desc()).limit(50).all()
        
        return jsonify({"executions": [e.to_dict() for e in executions]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch executions"}), 500


@workflow_bp.route("/workflows/analytics", methods=["GET"])
@jwt_required()
def get_workflow_analytics():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Get all workspaces for this user
        user_workspaces = Workspace.query.filter_by(user_id=user_id).all()
        workspace_ids = [w.id for w in user_workspaces]
        
        if not workspace_ids:
            return jsonify({
                "total_workflows": 0,
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_execution_time_ms": 0
            }), 200
        
        # Count workflows scoped to user's workspaces
        total_workflows = Workflow.query.filter(
            Workflow.workspace_id.in_(workspace_ids)
        ).count()
        
        # Get executions for user's workflows
        user_workflow_ids = [w.id for w in Workflow.query.filter(
            Workflow.workspace_id.in_(workspace_ids)
        ).all()]
        
        if not user_workflow_ids:
            return jsonify({
                "total_workflows": total_workflows,
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_execution_time_ms": 0
            }), 200
        
        total_executions = WorkflowExecution.query.filter(
            WorkflowExecution.workflow_id.in_(user_workflow_ids)
        ).count()
        
        successful_executions = WorkflowExecution.query.filter(
            WorkflowExecution.workflow_id.in_(user_workflow_ids),
            WorkflowExecution.status == "Success"
        ).count()
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        # Calculate average execution time
        executions_with_time = WorkflowExecution.query.filter(
            WorkflowExecution.workflow_id.in_(user_workflow_ids),
            WorkflowExecution.execution_time_ms != None
        ).all()
        
        avg_execution_time = 0
        if executions_with_time:
            total_time = sum(e.execution_time_ms for e in executions_with_time if e.execution_time_ms)
            avg_execution_time = total_time // len(executions_with_time) if executions_with_time else 0
        
        return jsonify({
            "total_workflows": total_workflows,
            "total_executions": total_executions,
            "success_rate": round(success_rate, 2),
            "avg_execution_time_ms": avg_execution_time
        }), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch analytics"}), 500


# --- WEBHOOK ROUTES ---
@workflow_bp.route("/workflows/<int:workflow_id>/webhooks", methods=["GET"])
@jwt_required()
def get_webhooks(workflow_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workflow = verify_workflow_ownership(workflow_id, user_id)
        if not workflow:
            return jsonify({"error": "Workflow not found"}), 404
        
        webhooks = Webhook.query.filter_by(workflow_id=workflow_id).all()
        return jsonify({"webhooks": [{
            "id": h.id,
            "endpoint_url": h.endpoint_url,
            "created_at": h.created_at.isoformat() if h.created_at else None
        } for h in webhooks]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch webhooks"}), 500


@workflow_bp.route("/workflows/<int:workflow_id>/webhooks", methods=["POST"])
@jwt_required()
def create_webhook(workflow_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        workflow = verify_workflow_ownership(workflow_id, user_id)
        if not workflow:
            return jsonify({"error": "Workflow not found"}), 404
        return jsonify({
            "status": "NOT_CONFIGURED",
            "error": "Webhook workflow execution is not configured."
        }), 501
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create webhook"}), 500


@workflow_bp.route("/webhooks/<int:webhook_id>", methods=["DELETE"])
@jwt_required()
def delete_webhook(webhook_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        webhook = Webhook.query.join(Workflow).join(Workspace).filter(
            Webhook.id == webhook_id,
            Workspace.user_id == user_id
        ).first()
        
        if not webhook:
            return jsonify({"error": "Webhook not found"}), 404
        
        db.session.delete(webhook)
        db.session.commit()
        return jsonify({"message": "Webhook deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete webhook"}), 500
