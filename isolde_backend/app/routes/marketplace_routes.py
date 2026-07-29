# app/routes/marketplace_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.marketplace_model import Developer, Plugin, PluginInstallation

marketplace_bp = Blueprint("marketplace_bp", __name__)

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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@marketplace_bp.route("/marketplace/plugins", methods=["POST"])
@jwt_required(optional=True)
def publish_plugin():
    try:
        user_id = get_jwt_identity() or 1
        data = request.get_json() or {}
        
        # Verify or create developer profile
        dev = Developer.query.filter_by(user_id=user_id).first()
        if not dev:
            dev = Developer(user_id=user_id, developer_name=data.get("developer_name", "Enterprise Dev"))
            db.session.add(dev)
            db.session.flush()

        plugin = Plugin(
            developer_id=dev.id,
            name=data.get("name", "Untitled Plugin"),
            plugin_key=data.get("plugin_key", f"plugin_{uuid.uuid4().hex[:6]}"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            category=data.get("category", "Productivity")
        )
        db.session.add(plugin)
        db.session.commit()
        return jsonify({"message": "Plugin published successfully", "plugin": plugin.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- INSTALLATION APIS ---
@marketplace_bp.route("/marketplace/install/<int:plugin_id>", methods=["POST"])
@jwt_required(optional=True)
def install_plugin(plugin_id):
    try:
        user_id = get_jwt_identity() or 1
        existing = PluginInstallation.query.filter_by(plugin_id=plugin_id, user_id=user_id).first()
        if existing:
            return jsonify({"message": "Plugin already installed"}), 200

        installation = PluginInstallation(plugin_id=plugin_id, user_id=user_id)
        
        # Increment download count
        plugin = Plugin.query.get(plugin_id)
        if plugin:
            plugin.downloads_count += 1

        db.session.add(installation)
        db.session.commit()
        return jsonify({"message": "Plugin installed successfully", "installation": installation.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@marketplace_bp.route("/marketplace/installed", methods=["GET"])
@jwt_required(optional=True)
def get_installed_plugins():
    try:
        user_id = get_jwt_identity() or 1
        installations = PluginInstallation.query.filter_by(user_id=user_id).all()
        plugin_ids = [i.plugin_id for i in installations]
        plugins = Plugin.query.filter(Plugin.id.in_(plugin_ids)).all() if plugin_ids else []
        
        return jsonify({"installed_plugins": [p.to_dict() for p in plugins]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500