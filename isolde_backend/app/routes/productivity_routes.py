# app/routes/productivity_routes.py
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.models.productivity_model import Task, CalendarEvent, Note, Bookmark

productivity_bp = Blueprint("productivity_bp", __name__)

# --- TASKS APIs ---
@productivity_bp.route("/productivity/tasks", methods=["GET"])
@jwt_required(optional=True)
def get_tasks():
    try:
        tasks = Task.query.order_by(Task.created_at.desc()).all()
        return jsonify({"tasks": [t.to_dict() for t in tasks]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@productivity_bp.route("/productivity/tasks", methods=["POST"])
@jwt_required(optional=True)
def create_task():
    try:
        data = request.get_json() or {}
        task = Task(
            title=data.get("title", "Untitled Task"),
            description=data.get("description"),
            priority=data.get("priority", "Medium"),
            status=data.get("status", "Pending"),
            due_date=data.get("due_date"),
            category=data.get("category", "General"),
            workspace_id=data.get("workspace_id"),
            project_id=data.get("project_id"),
            assigned_agent=data.get("assigned_agent")
        )
        db.session.add(task)
        db.session.commit()
        return jsonify({"message": "Task created", "task": task.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@productivity_bp.route("/productivity/tasks/<int:task_id>", methods=["PUT"])
@jwt_required(optional=True)
def update_task(task_id):
    try:
        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        
        data = request.get_json() or {}
        task.title = data.get("title", task.title)
        task.description = data.get("description", task.description)
        task.priority = data.get("priority", task.priority)
        task.status = data.get("status", task.status)
        task.due_date = data.get("due_date", task.due_date)
        task.category = data.get("category", task.category)
        
        if task.status == "Completed" and not task.completed_at:
            task.completed_at = datetime.utcnow()
        elif task.status != "Completed":
            task.completed_at = None

        db.session.commit()
        return jsonify({"message": "Task updated", "task": task.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@productivity_bp.route("/productivity/tasks/<int:task_id>", methods=["DELETE"])
@jwt_required(optional=True)
def delete_task(task_id):
    try:
        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        db.session.delete(task)
        db.session.commit()
        return jsonify({"message": "Task deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# --- CALENDAR APIs ---
@productivity_bp.route("/productivity/calendar", methods=["GET"])
@jwt_required(optional=True)
def get_calendar_events():
    try:
        events = CalendarEvent.query.order_by(CalendarEvent.start_time.asc()).all()
        return jsonify({"events": [e.to_dict() for e in events]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@productivity_bp.route("/productivity/calendar", methods=["POST"])
@jwt_required(optional=True)
def create_calendar_event():
    try:
        data = request.get_json() or {}
        event = CalendarEvent(
            title=data.get("title", "New Event"),
            description=data.get("description"),
            event_type=data.get("event_type", "Meeting"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            workspace_id=data.get("workspace_id")
        )
        db.session.add(event)
        db.session.commit()
        return jsonify({"message": "Event created", "event": event.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# --- NOTES APIs ---
@productivity_bp.route("/productivity/notes", methods=["GET"])
@jwt_required(optional=True)
def get_notes():
    try:
        notes = Note.query.order_by(Note.updated_at.desc()).all()
        return jsonify({"notes": [n.to_dict() for n in notes]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@productivity_bp.route("/productivity/notes", methods=["POST"])
@jwt_required(optional=True)
def create_note():
    try:
        data = request.get_json() or {}
        note = Note(
            title=data.get("title", "Untitled Note"),
            content=data.get("content", ""),
            folder=data.get("folder", "General"),
            tags=data.get("tags")
        )
        db.session.add(note)
        db.session.commit()
        return jsonify({"message": "Note created", "note": note.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# --- BOOKMARKS APIs ---
@productivity_bp.route("/productivity/bookmarks", methods=["GET"])
@jwt_required(optional=True)
def get_bookmarks():
    try:
        bookmarks = Bookmark.query.order_by(Bookmark.created_at.desc()).all()
        return jsonify({"bookmarks": [b.to_dict() for b in bookmarks]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@productivity_bp.route("/productivity/bookmarks", methods=["POST"])
@jwt_required(optional=True)
def create_bookmark():
    try:
        data = request.get_json() or {}
        bookmark = Bookmark(
            title=data.get("title", "Untitled Bookmark"),
            target_type=data.get("target_type", "Chat"),
            target_id=data.get("target_id", 1)
        )
        db.session.add(bookmark)
        db.session.commit()
        return jsonify({"message": "Bookmark created", "bookmark": bookmark.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500