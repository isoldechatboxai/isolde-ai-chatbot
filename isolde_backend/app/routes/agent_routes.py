# app/routes/agent_routes.py
from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.workspace_model import Agent, Workspace

agent_bp = Blueprint("agent_bp", __name__)


@agent_bp.route("/agent/list", methods=["GET"])
@jwt_required(optional=True)
def list_all_agents_global():
    """Returns all available agents across workspaces (Useful for global testing and UI dropdowns)."""
    try:
        agents = Agent.query.filter_by(is_active=True).all()
        return jsonify({"agents": [a.to_dict() for a in agents]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch agents", "details": str(e)}), 500


@agent_bp.route("/workspace/<int:workspace_id>/agents", methods=["GET"])
@jwt_required(optional=True)
def list_agents(workspace_id: int):
    try:
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        agents = (
            Agent.query.filter_by(workspace_id=workspace_id, is_active=True)
            .order_by(Agent.is_default.desc(), Agent.created_at.asc())
            .all()
        )
        return jsonify({"agents": [a.to_dict() for a in agents]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch agents", "details": str(e)}), 500


@agent_bp.route("/workspace/<int:workspace_id>/agents", methods=["POST"])
@jwt_required(optional=True)
def create_agent(workspace_id: int):
    try:
        workspace = Workspace.query.get(workspace_id)
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404

        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        system_prompt = (data.get("system_prompt") or "").strip()

        if not name or not system_prompt:
            return jsonify({"error": "Agent 'name' and 'system_prompt' are required"}), 400

        # If this agent is marked default, unset any existing default in this workspace
        if data.get("is_default"):
            Agent.query.filter_by(workspace_id=workspace_id, is_default=True).update(
                {"is_default": False}
            )

        agent = Agent(
            workspace_id=workspace_id,
            name=name,
            role_description=data.get("role_description", "").strip() or None,
            system_prompt=system_prompt,
            avatar_emoji=data.get("avatar_emoji", "🤖"),
            is_default=bool(data.get("is_default", False)),
        )
        db.session.add(agent)
        db.session.commit()
        return jsonify({"message": "Agent created", "agent": agent.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create agent", "details": str(e)}), 500


@agent_bp.route("/agent/<int:agent_id>", methods=["PUT"])
@jwt_required(optional=True)
def update_agent(agent_id: int):
    try:
        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        data = request.get_json() or {}
        if "name" in data and data["name"].strip():
            agent.name = data["name"].strip()
        if "role_description" in data:
            agent.role_description = data["role_description"].strip() or None
        if "system_prompt" in data and data["system_prompt"].strip():
            agent.system_prompt = data["system_prompt"].strip()
        if "avatar_emoji" in data:
            agent.avatar_emoji = data["avatar_emoji"]
        if "is_active" in data:
            agent.is_active = bool(data["is_active"])
        if "is_default" in data and data["is_default"]:
            Agent.query.filter_by(workspace_id=agent.workspace_id, is_default=True).update(
                {"is_default": False}
            )
            agent.is_default = True

        db.session.commit()
        return jsonify({"message": "Agent updated", "agent": agent.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to update agent", "details": str(e)}), 500


@agent_bp.route("/agent/<int:agent_id>", methods=["DELETE"])
@jwt_required(optional=True)
def delete_agent(agent_id: int):
    try:
        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        db.session.delete(agent)
        db.session.commit()
        return jsonify({"message": "Agent deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete agent", "details": str(e)}), 500


@agent_bp.route("/agent/<int:agent_id>/activate", methods=["POST"])
@jwt_required(optional=True)
def activate_agent(agent_id: int):
    """
    Instant Agent Switching: marks this agent as the 'active' one for the
    current user session. provider_router.py reads this to inject the
    correct system_prompt into the next AI call — no page reload needed.
    """
    try:
        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        user_id = get_jwt_identity() or "guest_user"

        # Stored in Flask session, keyed by user, so multiple users switching
        # agents concurrently never collide with each other.
        session[f"active_agent_{user_id}"] = agent.id

        return jsonify({
            "message": f"Switched to agent: {agent.name}",
            "active_agent": agent.to_dict()
        }), 200
    except Exception as e:
        return jsonify({"error": "Failed to switch agent", "details": str(e)}), 500


@agent_bp.route("/agent/active", methods=["GET"])
@jwt_required(optional=True)
def get_active_agent():
    """Returns whichever agent is currently active for this user (or None)."""
    try:
        user_id = get_jwt_identity() or "guest_user"
        agent_id = session.get(f"active_agent_{user_id}")

        if not agent_id:
            return jsonify({"active_agent": None}), 200

        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({"active_agent": None}), 200

        return jsonify({"active_agent": agent.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch active agent", "details": str(e)}), 500