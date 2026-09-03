from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.productivity_model import Bookmark, CalendarEvent, Note, Task
from app.models.workspace_model import Project, Workspace

productivity_bp = Blueprint("productivity_bp", __name__)


def _user_id():
    return str(get_jwt_identity())


def _owned_scope(data, user_id):
    workspace_id = data.get("workspace_id")
    project_id = data.get("project_id")
    if workspace_id and not Workspace.query.filter_by(id=workspace_id, user_id=user_id).first():
        return False
    if project_id and not Project.query.join(Workspace).filter(
        Project.id == project_id, Workspace.user_id == user_id
    ).first():
        return False
    return True


@productivity_bp.route("/productivity/tasks", methods=["GET"])
@jwt_required()
def get_tasks():
    tasks = Task.query.filter_by(user_id=_user_id()).order_by(Task.created_at.desc()).all()
    return jsonify({"tasks": [item.to_dict() for item in tasks]}), 200


@productivity_bp.route("/productivity/tasks", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json(silent=True) or {}
    user_id = _user_id()
    if not _owned_scope(data, user_id):
        return jsonify({"error": "Workspace or project not found."}), 404
    title = str(data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Task title is required."}), 400
    task = Task(
        user_id=user_id, title=title, description=data.get("description"),
        priority=data.get("priority", "Medium"), status=data.get("status", "Pending"),
        due_date=data.get("due_date"), category=data.get("category", "General"),
        workspace_id=data.get("workspace_id"), project_id=data.get("project_id"),
        assigned_agent=data.get("assigned_agent"),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"message": "Task created", "task": task.to_dict()}), 201


@productivity_bp.route("/productivity/tasks/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=_user_id()).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404
    data = request.get_json(silent=True) or {}
    for field in ("title", "description", "priority", "status", "due_date", "category"):
        if field in data:
            setattr(task, field, data[field])
    task.completed_at = datetime.now(timezone.utc) if task.status == "Completed" else None
    db.session.commit()
    return jsonify({"message": "Task updated", "task": task.to_dict()}), 200


@productivity_bp.route("/productivity/tasks/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=_user_id()).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


@productivity_bp.route("/productivity/calendar", methods=["GET"])
@jwt_required()
def get_calendar_events():
    events = CalendarEvent.query.filter_by(user_id=_user_id()).order_by(CalendarEvent.start_time.asc()).all()
    return jsonify({"events": [item.to_dict() for item in events]}), 200


@productivity_bp.route("/productivity/calendar", methods=["POST"])
@jwt_required()
def create_calendar_event():
    data = request.get_json(silent=True) or {}
    user_id = _user_id()
    if not _owned_scope(data, user_id):
        return jsonify({"error": "Workspace not found."}), 404
    if not data.get("start_time"):
        return jsonify({"error": "start_time is required."}), 400
    event = CalendarEvent(
        user_id=user_id, title=str(data.get("title") or "New Event")[:255],
        description=data.get("description"), event_type=data.get("event_type", "Meeting"),
        start_time=data["start_time"], end_time=data.get("end_time"), workspace_id=data.get("workspace_id"),
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({"message": "Event created", "event": event.to_dict()}), 201


@productivity_bp.route("/productivity/notes", methods=["GET"])
@jwt_required()
def get_notes():
    notes = Note.query.filter_by(user_id=_user_id()).order_by(Note.updated_at.desc()).all()
    return jsonify({"notes": [item.to_dict() for item in notes]}), 200


@productivity_bp.route("/productivity/notes", methods=["POST"])
@jwt_required()
def create_note():
    data = request.get_json(silent=True) or {}
    user_id = _user_id()
    if not _owned_scope(data, user_id):
        return jsonify({"error": "Workspace not found."}), 404
    note = Note(
        user_id=user_id, workspace_id=data.get("workspace_id"),
        title=str(data.get("title") or "Untitled Note")[:255], content=data.get("content", ""),
        folder=data.get("folder", "General"), tags=data.get("tags"),
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({"message": "Note created", "note": note.to_dict()}), 201


@productivity_bp.route("/productivity/bookmarks", methods=["GET"])
@jwt_required()
def get_bookmarks():
    bookmarks = Bookmark.query.filter_by(user_id=_user_id()).order_by(Bookmark.created_at.desc()).all()
    return jsonify({"bookmarks": [item.to_dict() for item in bookmarks]}), 200


@productivity_bp.route("/productivity/bookmarks", methods=["POST"])
@jwt_required()
def create_bookmark():
    data = request.get_json(silent=True) or {}
    target_id = data.get("target_id")
    if not isinstance(target_id, int) or target_id <= 0:
        return jsonify({"error": "A valid target_id is required."}), 400
    bookmark = Bookmark(
        user_id=_user_id(), title=str(data.get("title") or "Untitled Bookmark")[:255],
        target_type=data.get("target_type", "Chat"), target_id=target_id,
    )
    db.session.add(bookmark)
    db.session.commit()
    return jsonify({"message": "Bookmark created", "bookmark": bookmark.to_dict()}), 201
