from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.plugin_manager import plugin_manager
from app.security.authorization import admin_required


plugin_bp = Blueprint("plugin_bp", __name__)


@plugin_bp.route("/plugins/registry", methods=["GET"])
@jwt_required(optional=True)
def list_registered_plugins():
    if current_app.config.get("IS_PRODUCTION"):
        return jsonify({"status": "error", "error": "Runtime plugins are disabled in production."}), 501
    try:
        return jsonify({
            "status": "success",
            "plugins": plugin_manager.list_plugins()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@plugin_bp.route("/plugins/registry/installed", methods=["GET"])
@jwt_required(optional=True)
def list_installed_plugins():
    if current_app.config.get("IS_PRODUCTION"):
        return jsonify({"status": "error", "error": "Runtime plugins are disabled in production."}), 501
    """
    Return currently registered/installed plugins.
    """
    try:
        plugins = plugin_manager.list_plugins()

        return jsonify({
            "status": "success",
            "installed_plugins": plugins
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@plugin_bp.route("/plugins/registry/install", methods=["POST"])
@jwt_required()
def install_plugin():
    """
    Validate and activate a plugin by name from the registry.
    """
    try:
        data = request.get_json(silent=True) or {}
        plugin_name = (data.get("plugin_name") or "").strip()

        if not plugin_name:
            return jsonify({
                "status": "error",
                "error": "plugin_name is required"
            }), 400

        plugins = plugin_manager.list_plugins()

        plugin_names = []

        for plugin in plugins:
            if isinstance(plugin, dict):
                name = plugin.get("name")
                if name:
                    plugin_names.append(str(name))

            elif isinstance(plugin, str):
                plugin_names.append(plugin)

        if plugin_name not in plugin_names:
            return jsonify({
                "status": "error",
                "error": f"Plugin '{plugin_name}' not found in registry."
            }), 404

        return jsonify({
            "status": "unavailable",
            "error": "Persistent plugin installation is not configured."
        }), 501

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@plugin_bp.route("/plugins/registry/load", methods=["POST"])
@admin_required
def load_plugins():
    if current_app.config.get("IS_PRODUCTION"):
        return jsonify({"status": "error", "error": "Runtime plugin loading is disabled in production."}), 501
    try:
        data = request.get_json(silent=True) or {}
        directory = data.get("directory")

        if not directory:
            return jsonify({
                "status": "error",
                "error": "directory is required"
            }), 400

        count = plugin_manager.load_plugins_from_directory(directory)

        return jsonify({
            "status": "success",
            "loaded": count
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@plugin_bp.route(
    "/plugins/registry/<string:plugin_name>/execute",
    methods=["POST"]
)
@admin_required
def execute_plugin(plugin_name):
    if current_app.config.get("IS_PRODUCTION"):
        return jsonify({"status": "error", "error": "Runtime plugins are disabled in production."}), 501
    try:
        data = request.get_json(silent=True) or {}

        args = data.get("args", [])
        kwargs = data.get("kwargs", {})

        if not isinstance(args, list):
            return jsonify({
                "status": "error",
                "error": "args must be a list"
            }), 400

        if not isinstance(kwargs, dict):
            return jsonify({
                "status": "error",
                "error": "kwargs must be an object"
            }), 400

        result = plugin_manager.execute_plugin(
            plugin_name,
            *args,
            **kwargs
        )

        return jsonify({
            "status": "success",
            "result": result
        }), 200

    except ValueError as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 404

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@plugin_bp.route(
    "/plugins/registry/<string:plugin_name>",
    methods=["DELETE"]
)
@admin_required
def unregister_plugin(plugin_name):
    if current_app.config.get("IS_PRODUCTION"):
        return jsonify({"status": "error", "error": "Runtime plugins are disabled in production."}), 501
    try:
        ok = plugin_manager.unregister_plugin(plugin_name)

        if not ok:
            return jsonify({
                "status": "error",
                "error": "Plugin not found"
            }), 404

        return jsonify({
            "status": "success",
            "message": f"Plugin '{plugin_name}' unregistered."
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
