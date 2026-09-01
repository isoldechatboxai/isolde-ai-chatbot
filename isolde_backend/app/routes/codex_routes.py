from flask import Blueprint, request, jsonify

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
)

from app.services.codex_service import (
    create_project,
    list_projects,
    get_project,
    update_project,
    delete_project,
    list_files,
    read_file,
    save_file,
    rename_file,
    delete_file,
    create_task,
    get_task,
    update_task,
    cancel_task,
    execute_task,
)


codex_bp = Blueprint(
    "codex",
    __name__,
)


def _get_user_id():
    user_id = get_jwt_identity()
    return str(user_id) if user_id else None


# ---------------------------------------------------------------------------
# PROJECTS
# ---------------------------------------------------------------------------

@codex_bp.route(
    "/codex/projects",
    methods=["POST"],
    strict_slashes=False,
)
@jwt_required()
def api_create_project():

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    data = request.get_json(silent=True) or {}

    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "")
    workspace_id = data.get("workspace_id")

    if not name:
        return jsonify({
            "success": False,
            "message": "Project name is required.",
        }), 400

    result = create_project(
        user_id,
        name,
        description,
        workspace_id,
    )

    return jsonify(result), (
        201 if result.get("success") else 400
    )


@codex_bp.route(
    "/codex/projects",
    methods=["GET"],
    strict_slashes=False,
)
@jwt_required()
def api_list_projects():

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    return jsonify({
        "success": True,
        "data": list_projects(user_id),
    }), 200


@codex_bp.route(
    "/codex/projects/<int:project_id>",
    methods=["GET"],
    strict_slashes=False,
)
@jwt_required()
def api_get_project(project_id):

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    project = get_project(
        user_id,
        project_id,
    )

    if not project:
        return jsonify({
            "success": False,
            "message": "Project not found or access denied.",
        }), 404

    return jsonify({
        "success": True,
        "data": project.to_dict(),
    }), 200


@codex_bp.route("/codex/projects/<int:project_id>", methods=["PATCH"], strict_slashes=False)
@jwt_required()
def api_update_project(project_id):
    data = request.get_json(silent=True) or {}
    allowed = {key: data[key] for key in ("name", "description", "status") if key in data}
    if not allowed or any(not isinstance(value, str) for value in allowed.values()):
        return jsonify({"success": False, "message": "Provide text project fields to update."}), 400
    result = update_project(_get_user_id(), project_id, **allowed)
    return jsonify(result), 200 if result.get("success") else (404 if "not found" in result["message"].lower() else 400)


@codex_bp.route("/codex/projects/<int:project_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def api_delete_project(project_id):
    result = delete_project(_get_user_id(), project_id)
    return jsonify(result), 200 if result.get("success") else 404


# ---------------------------------------------------------------------------
# FILES
# ---------------------------------------------------------------------------

@codex_bp.route(
    "/codex/projects/<int:project_id>/files",
    methods=["GET"],
    strict_slashes=False,
)
@jwt_required()
def api_list_files(project_id):

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    if get_project(user_id, project_id) is None:
        return jsonify({
            "success": False,
            "message": "Project not found or access denied.",
        }), 404

    return jsonify({
        "success": True,
        "data": list_files(
            user_id,
            project_id,
        ),
    }), 200


@codex_bp.route(
    "/codex/projects/<int:project_id>/files",
    methods=["POST"],
    strict_slashes=False,
)
@jwt_required()
def api_save_file(project_id):

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    data = request.get_json(silent=True) or {}

    file_path = str(
        data.get("file_path") or ""
    ).strip()

    content = data.get("content", "")

    if not file_path:
        return jsonify({
            "success": False,
            "message": "file_path is required.",
        }), 400

    if not isinstance(content, str):
        return jsonify({
            "success": False,
            "message": "content must be text.",
        }), 400

    result = save_file(
        user_id,
        project_id,
        file_path,
        content,
        modified_by=user_id,
    )

    if result.get("success"):
        return jsonify(result), 201
    return jsonify(result), 404 if "not found" in result.get("message", "").lower() else 400


@codex_bp.route(
    "/codex/projects/<int:project_id>/files/<path:file_path>",
    methods=["GET"],
    strict_slashes=False,
)
@jwt_required()
def api_read_file(
    project_id,
    file_path,
):

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    result = read_file(
        user_id,
        project_id,
        file_path,
    )

    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 404 if "not found" in result.get("message", "").lower() else 400


@codex_bp.route("/codex/projects/<int:project_id>/files/<path:file_path>", methods=["PATCH"], strict_slashes=False)
@jwt_required()
def api_update_file(project_id, file_path):
    data = request.get_json(silent=True) or {}
    if "new_file_path" in data:
        if not isinstance(data["new_file_path"], str):
            return jsonify({"success": False, "message": "new_file_path must be text."}), 400
        result = rename_file(_get_user_id(), project_id, file_path, data["new_file_path"])
    elif "content" in data and isinstance(data["content"], str):
        result = save_file(_get_user_id(), project_id, file_path, data["content"], modified_by=_get_user_id())
    else:
        return jsonify({"success": False, "message": "Provide content or new_file_path."}), 400
    if result.get("success"):
        return jsonify(result), 200
    message = result.get("message", "").lower()
    return jsonify(result), 404 if "not found" in message else (409 if "already exists" in message else 400)


@codex_bp.route("/codex/projects/<int:project_id>/files/<path:file_path>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def api_delete_file(project_id, file_path):
    result = delete_file(_get_user_id(), project_id, file_path)
    return jsonify(result), 200 if result.get("success") else (404 if "not found" in result.get("message", "").lower() else 400)


# ---------------------------------------------------------------------------
# TASKS
# ---------------------------------------------------------------------------

@codex_bp.route(
    "/codex/projects/<int:project_id>/tasks",
    methods=["POST"],
    strict_slashes=False,
)
@jwt_required()
def api_create_task(project_id):

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    data = request.get_json(silent=True) or {}

    instruction = str(
        data.get("instruction") or ""
    ).strip()

    if not instruction:
        return jsonify({
            "success": False,
            "message": "instruction is required.",
        }), 400

    result = create_task(
        user_id,
        project_id,
        instruction,
    )

    return jsonify(result), (
        201 if result.get("success") else 400
    )


@codex_bp.route(
    "/codex/projects/<int:project_id>/tasks/<int:task_id>",
    methods=["GET"],
    strict_slashes=False,
)
@jwt_required()
def api_get_task(
    project_id,
    task_id,
):

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    task = get_task(
        user_id,
        project_id,
        task_id,
    )

    if not task:
        return jsonify({
            "success": False,
            "message": "Task not found or access denied.",
        }), 404

    return jsonify({
        "success": True,
        "data": task.to_dict(),
    }), 200


@codex_bp.route("/codex/projects/<int:project_id>/tasks/<int:task_id>", methods=["PATCH"], strict_slashes=False)
@jwt_required()
def api_update_task(project_id, task_id):
    data = request.get_json(silent=True) or {}
    result = update_task(_get_user_id(), project_id, task_id, data.get("instruction"))
    if result.get("success"):
        return jsonify(result), 200
    message = result.get("message", "").lower()
    return jsonify(result), 404 if "not found" in message else (409 if "cannot" in message else 400)


@codex_bp.route("/codex/projects/<int:project_id>/tasks/<int:task_id>/cancel", methods=["POST"], strict_slashes=False)
@jwt_required()
def api_cancel_task(project_id, task_id):
    result = cancel_task(_get_user_id(), project_id, task_id)
    if result.get("success"):
        return jsonify(result), 200
    message = result.get("message", "").lower()
    return jsonify(result), 404 if "not found" in message else 409


@codex_bp.route(
    "/codex/projects/<int:project_id>/tasks/<int:task_id>/execute",
    methods=["POST"],
    strict_slashes=False,
)
@jwt_required()
def api_execute_task(
    project_id,
    task_id,
):

    user_id = _get_user_id()

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required.",
        }), 401

    data = request.get_json(silent=True) or {}

    apply_changes = data.get(
        "apply_changes",
        True,
    )

    if not isinstance(apply_changes, bool):
        return jsonify({
            "success": False,
            "message": "apply_changes must be boolean.",
        }), 400

    result = execute_task(
        user_id=user_id,
        project_id=project_id,
        task_id=task_id,
        apply_changes=apply_changes,
    )

    if result.get("success"):
        return jsonify(result), 200

    message = result.get("message", "")

    if "not found" in message.lower():
        status = 404
    elif "cannot execute" in message.lower():
        status = 409
    else:
        status = 422

    return jsonify(result), status
