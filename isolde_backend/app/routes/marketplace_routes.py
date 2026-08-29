# app/routes/marketplace_routes.py
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app import db
from app.models.marketplace_model import Developer, Plugin, PluginInstallation

marketplace_bp = Blueprint("marketplace_bp", __name__)

def get_current_user_id():
    """Safely get the authenticated user ID. Returns None if not authenticated."""
    try:
        verify_jwt_in_request(optional=True)
        return get_jwt_identity()
    except Exception:
        return None

# --- MARKETPLACE STORE APIS ---
@marketplace_bp.route("/marketplace/plugins", methods=["GET"])
@jwt_required(optional=True)
def get_marketplace_plugins():
    try:
        category = request.args.get("category")
        query = Plugin.query.filter_by(status="Published")
        if category and category != "All":
            query = query.filter_by(category=category)
        
        plugins = query.order_by(Plugin.downloads_count.desc()).all()
        return jsonify({"plugins": [p.to_dict() for p in plugins]}), 200
    except Exception:
        current_app.logger.exception("Marketplace listing failed.")
        return jsonify({"error": "Marketplace listing is unavailable."}), 500

@marketplace_bp.route("/marketplace/plugins", methods=["POST"])
@jwt_required()
def publish_plugin():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        # Validate required fields
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Plugin name is required"}), 400
        
        plugin_key = (data.get("plugin_key") or "").strip()
        if not plugin_key:
            plugin_key = f"plugin_{uuid.uuid4().hex[:6]}"
        
        # Verify or create developer profile
        dev = Developer.query.filter_by(user_id=user_id).first()
        if not dev:
            developer_name = (data.get("developer_name") or "").strip()
            if not developer_name:
                return jsonify({"error": "Developer name is required"}), 400
            dev = Developer(user_id=user_id, developer_name=developer_name)
            db.session.add(dev)
            db.session.flush()

        plugin = Plugin(
            developer_id=dev.id,
            name=name,
            plugin_key=plugin_key,
            version=(data.get("version") or "1.0.0").strip(),
            description=(data.get("description") or "").strip() or None,
            category=(data.get("category") or "Productivity").strip()
        )
        db.session.add(plugin)
        db.session.commit()
        return jsonify({"message": "Plugin published successfully", "plugin": plugin.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to publish plugin"}), 500

# --- INSTALLATION APIS ---
@marketplace_bp.route("/marketplace/install/<int:plugin_id>", methods=["POST"])
@jwt_required()
def install_plugin(plugin_id):
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        # Verify plugin exists and is published
        plugin = db.session.get(Plugin, plugin_id)
        if not plugin:
            return jsonify({"error": "Plugin not found"}), 404
        if plugin.status != "Published":
            return jsonify({"error": "Plugin is not available for installation"}), 403
        
        existing = PluginInstallation.query.filter_by(plugin_id=plugin_id, user_id=user_id).first()
        if existing:
            return jsonify({"message": "Plugin already installed", "installation": existing.to_dict()}), 200

        installation = PluginInstallation(plugin_id=plugin_id, user_id=user_id)
        
        # Increment download count
        plugin.downloads_count += 1

        db.session.add(installation)
        db.session.commit()
        return jsonify({"message": "Plugin installed successfully", "installation": installation.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to install plugin"}), 500

@marketplace_bp.route("/marketplace/installed", methods=["GET"])
@jwt_required()
def get_installed_plugins():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        installations = PluginInstallation.query.filter_by(user_id=user_id).all()
        plugin_ids = [i.plugin_id for i in installations]
        plugins = Plugin.query.filter(Plugin.id.in_(plugin_ids)).all() if plugin_ids else []
        
        return jsonify({"installed_plugins": [p.to_dict() for p in plugins]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch installed plugins"}), 500
