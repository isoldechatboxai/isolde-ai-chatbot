from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.plugin_manager import plugin_manager

plugin_bp = Blueprint("plugin_bp", __name__)


@plugin_bp.route("/plugins/registry", methods=["GET"])
@jwt_required(optional=True)
def list_registered_plugins():
    try:
        return jsonify({"plugins": plugin_manager.list_plugins()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@plugin_bp.route("/plugins/registry/load", methods=["POST"])
@jwt_required(optional=True)
def load_plugins():
    try:
        data = request.get_json() or {}
        directory = data.get("directory")
        count = plugin_manager.load_plugins_from_directory(directory)
        return jsonify({"status": "success", "loaded": count}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@plugin_bp.route("/plugins/registry/<string:plugin_name>/execute", methods=["POST"])
@jwt_required(optional=True)
def execute_plugin(plugin_name):
    try:
        data = request.get_json() or {}
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        result = plugin_manager.execute_plugin(plugin_name, *args, **kwargs)
        return jsonify({"status": "success", "result": result}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@plugin_bp.route("/plugins/registry/<string:plugin_name>", methods=["DELETE"])
@jwt_required(optional=True)
def unregister_plugin(plugin_name):
    try:
        ok = plugin_manager.unregister_plugin(plugin_name)
        if not ok:
            return jsonify({"error": "Plugin not found"}), 404
        return jsonify({"status": "success", "message": f"Plugin '{plugin_name}' unregistered."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500