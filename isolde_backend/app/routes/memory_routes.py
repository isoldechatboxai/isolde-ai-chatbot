# app/routes/memory_routes.py
from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.memory_model import UserMemory
from app.services.provider_router import generate_reply

import json
import csv
import io

memory_bp = Blueprint("memory_bp", __name__)


def _current_user_id():
    user_id = get_jwt_identity()

    if user_id is None:
        return None

    user_id = str(user_id).strip()

    if not user_id:
        return None

    return user_id


def _get_json_payload():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return {}

    return payload


def _safe_str(value, max_length=None):
    if value is None:
        return ""

    text = str(value).strip()

    if max_length is not None and len(text) > max_length:
        text = text[:max_length]

    return text


def _safe_confidence(value, default=0.0):
    try:
        confidence = float(value)
    except Exception:
        confidence = float(default)

    if confidence < 0.0:
        confidence = 0.0

    if confidence > 1.0:
        confidence = 1.0

    return confidence


def _as_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def _escape_like(value):
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def extract_memory_with_ai(raw_text):
    """
    Uses Universal AI wrapper to intelligently parse a statement into
    Category, Key, Value, and Confidence.
    """
    try:
        prompt = f"""
Analyze the following user statement and extract memory information in strict JSON format.
Categories allowed: Personal, Location, Education, Work, Preference, Goals, Health, Custom.
Return ONLY a JSON object with keys: "category", "key", "value", "confidence".
Statement: "{raw_text}"
"""

        response_text = generate_reply(
            prompt,
            system_context="You are a precise JSON parser. Return strict JSON only."
        )

        text = str(response_text or "").strip()

        if text.startswith("```"):
            parts = text.split("```")

            if len(parts) > 1:
                text = parts[1]

                if text.startswith("json"):
                    text = text[4:].strip()

        data = json.loads(text)

        if not isinstance(data, dict):
            raise ValueError("Invalid AI extraction payload")

        return {
            "category": _safe_str(data.get("category"), 50) or "Personal",
            "key": _safe_str(data.get("key"), 100) or "General",
            "value": _safe_str(data.get("value"), 2000) or raw_text,
            "confidence": _safe_confidence(data.get("confidence", 0.95), 0.0),
        }
    except Exception:
        return {
            "category": "Personal",
            "key": "General",
            "value": raw_text,
            "confidence": 0.85,
        }


@memory_bp.route("/memory/save", methods=["POST"], strict_slashes=False)
@jwt_required()
def save_memory():
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = _get_json_payload()

    memory_text = _safe_str(data.get("memory"), 2000)

    if not memory_text:
        return jsonify({"error": "Memory content cannot be empty"}), 400

    extracted = extract_memory_with_ai(memory_text)

    category = _safe_str(data.get("category"), 50) or extracted["category"] or "Personal"
    key = _safe_str(data.get("key"), 100) or extracted["key"] or "General"
    value = _safe_str(data.get("value"), 2000) or extracted["value"] or memory_text

    if "confidence_score" in data:
        confidence_raw = data.get("confidence_score")
    else:
        confidence_raw = extracted["confidence"]

    confidence = _safe_confidence(confidence_raw, 0.0)

    if confidence < 0.7:
        return jsonify({
            "message": "Memory confidence too low to save automatically",
            "confidence": confidence
        }), 200

    try:
        existing = UserMemory.query.filter_by(user_id=user_id, key=key).first()

        if existing:
            existing_value = str(existing.value or "").lower()
            new_value = str(value or "").lower()

            if existing_value == new_value:
                return jsonify({
                    "message": "Memory already up-to-date",
                    "memory": existing.to_dict()
                }), 200

            history = []

            try:
                if existing.version_history:
                    parsed_history = json.loads(existing.version_history)

                    if isinstance(parsed_history, list):
                        history = parsed_history
            except Exception:
                history = []

            history.append({
                "value": existing.value,
                "updated_at": existing.updated_at.isoformat() if existing.updated_at else ""
            })

            existing.version_history = json.dumps(history)
            existing.value = value
            existing.memory = f"{key}: {value}"
            existing.category = category
            existing.confidence_score = confidence

            db.session.commit()

            return jsonify({
                "message": "Memory updated with versioning",
                "memory": existing.to_dict()
            }), 200

        new_memory = UserMemory(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            memory=f"{key}: {value}" if key and value else memory_text,
            confidence_score=confidence,
            is_pinned=_as_bool(data.get("is_pinned", False))
        )

        db.session.add(new_memory)
        db.session.commit()

        return jsonify({
            "message": "Structured memory saved successfully",
            "memory": new_memory.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Memory save error: {e}")

        return jsonify({
            "error": "Failed to save memory due to a server error."
        }), 500


@memory_bp.route("/memory/list", methods=["GET"], strict_slashes=False)
@jwt_required()
def list_memories():
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"memories": []}), 200

    search_query = _safe_str(request.args.get("search", ""), 200)
    category_filter = _safe_str(request.args.get("category", ""), 50)

    try:
        query = UserMemory.query.filter_by(user_id=user_id)

        if category_filter and category_filter.lower() != "all":
            if category_filter.lower() == "uncategorized":
                query = query.filter(
                    db.or_(
                        UserMemory.category.is_(None),
                        UserMemory.category == ""
                    )
                )
            else:
                query = query.filter(UserMemory.category == category_filter)

        if search_query:
            escaped_query = _escape_like(search_query)

            query = query.filter(
                db.or_(
                    UserMemory.key.ilike(f"%{escaped_query}%", escape="\\"),
                    UserMemory.value.ilike(f"%{escaped_query}%", escape="\\"),
                    UserMemory.category.ilike(f"%{escaped_query}%", escape="\\"),
                    UserMemory.memory.ilike(f"%{escaped_query}%", escape="\\")
                )
            )

        memories = (
            query
            .order_by(
                UserMemory.is_pinned.desc(),
                UserMemory.updated_at.desc()
            )
            .all()
        )

        return jsonify({
            "memories": [memory.to_dict() for memory in memories]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Memory list error: {e}")

        return jsonify({
            "error": "Failed to load memories due to a server error."
        }), 500


@memory_bp.route("/memory/categories", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_memory_categories():
    user_id = _current_user_id()

    if not user_id:
        return jsonify({
            "total": 0,
            "categories": {}
        }), 200

    try:
        rows = (
            db.session.query(
                UserMemory.category,
                db.func.count(UserMemory.id)
            )
            .filter(UserMemory.user_id == user_id)
            .group_by(UserMemory.category)
            .all()
        )

        counts = {}

        for category, count in rows:
            label = category if category else "Uncategorized"
            counts[label] = counts.get(label, 0) + count

        total = sum(counts.values())

        return jsonify({
            "total": total,
            "categories": counts
        }), 200
    except Exception as e:
        current_app.logger.error(f"Memory categories error: {e}")

        return jsonify({
            "error": "Failed to fetch categories due to a server error."
        }), 500


@memory_bp.route("/memory/stats", methods=["GET"], strict_slashes=False)
@jwt_required()
def memory_stats():
    user_id = _current_user_id()

    if not user_id:
        return jsonify({
            "total_memories": 0,
            "pinned_memories": 0,
            "total_categories": 0,
            "last_updated": None
        }), 200

    try:
        memories = UserMemory.query.filter_by(user_id=user_id).all()

        total = len(memories)
        pinned = sum(1 for memory in memories if memory.is_pinned)
        categories = len(set(memory.category for memory in memories))
        last_updated = max((memory.updated_at for memory in memories), default=None)

        return jsonify({
            "total_memories": total,
            "pinned_memories": pinned,
            "total_categories": categories,
            "last_updated": last_updated.isoformat() if last_updated else None
        }), 200
    except Exception as e:
        current_app.logger.error(f"Memory stats error: {e}")

        return jsonify({
            "error": "Failed to load memory stats due to a server error."
        }), 500


@memory_bp.route("/memory/<int:memory_id>/pin", methods=["PATCH"], strict_slashes=False)
@jwt_required()
def toggle_pin_memory(memory_id):
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        memory = UserMemory.query.filter_by(
            id=memory_id,
            user_id=user_id
        ).first()
    except Exception as e:
        current_app.logger.error(f"Memory pin lookup error: {e}")

        return jsonify({
            "error": "Failed to update memory due to a server error."
        }), 500

    if not memory:
        return jsonify({"error": "Memory not found"}), 404

    try:
        memory.is_pinned = not bool(memory.is_pinned)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Memory pin update error: {e}")

        return jsonify({
            "error": "Failed to update memory due to a server error."
        }), 500

    return jsonify({
        "message": "Pin status updated",
        "memory": memory.to_dict()
    }), 200


@memory_bp.route("/memory/<int:memory_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def delete_memory(memory_id):
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        memory = UserMemory.query.filter_by(
            id=memory_id,
            user_id=user_id
        ).first()
    except Exception as e:
        current_app.logger.error(f"Memory delete lookup error: {e}")

        return jsonify({
            "error": "Failed to delete memory due to a server error."
        }), 500

    if not memory:
        return jsonify({"error": "Memory not found"}), 404

    try:
        db.session.delete(memory)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Memory delete error: {e}")

        return jsonify({
            "error": "Failed to delete memory due to a server error."
        }), 500

    return jsonify({
        "message": "Memory deleted successfully"
    }), 200


@memory_bp.route(
    "/memory/category/<string:category_name>",
    methods=["DELETE"],
    strict_slashes=False
)
@jwt_required()
def delete_category(category_name):
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    category_name = _safe_str(category_name, 50)

    if not category_name:
        return jsonify({"error": "Category name cannot be empty"}), 400

    try:
        UserMemory.query.filter_by(
            user_id=user_id,
            category=category_name
        ).delete()

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Memory category delete error: {e}")

        return jsonify({
            "error": "Failed to delete category memories due to a server error."
        }), 500

    return jsonify({
        "message": f"Category {category_name} cleared successfully"
    }), 200


@memory_bp.route("/memory/all", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def clear_all_memories():
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        UserMemory.query.filter_by(user_id=user_id).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Memory clear-all error: {e}")

        return jsonify({
            "error": "Failed to clear memories due to a server error."
        }), 500

    return jsonify({
        "message": "All memories cleared successfully"
    }), 200


@memory_bp.route(
    "/memory/export/<string:file_format>",
    methods=["GET"],
    strict_slashes=False
)
@jwt_required()
def export_memories(file_format):
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    file_format = _safe_str(file_format, 10).lower()

    if file_format not in {"json", "csv"}:
        return jsonify({"error": "Invalid format. Use json or csv."}), 400

    try:
        memories = UserMemory.query.filter_by(user_id=user_id).all()
        data = [memory.to_dict() for memory in memories]
    except Exception as e:
        current_app.logger.error(f"Memory export error: {e}")

        return jsonify({
            "error": "Failed to export memories due to a server error."
        }), 500

    if file_format == "json":
        return jsonify({"memories": data}), 200

    si = io.StringIO()

    fieldnames = [
        "id",
        "category",
        "key",
        "value",
        "confidence_score",
        "is_pinned",
        "updated_at"
    ]

    writer = csv.DictWriter(si, fieldnames=fieldnames)
    writer.writeheader()

    for row in data:
        writer.writerow({key: row.get(key, "") for key in fieldnames})

    output = si.getvalue()

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment;filename=memories.csv"
        }
    )


@memory_bp.route("/memory/import", methods=["POST"], strict_slashes=False)
@jwt_required()
def import_memories():
    user_id = _current_user_id()

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = _get_json_payload()
    mem_list = data.get("memories", [])

    if not isinstance(mem_list, list):
        return jsonify({"error": "memories must be a list."}), 400

    count = 0

    try:
        for item in mem_list:
            if not isinstance(item, dict):
                continue

            key = _safe_str(item.get("key"), 100)
            value = _safe_str(item.get("value"), 2000)

            if not key or not value:
                continue

            existing = UserMemory.query.filter_by(user_id=user_id, key=key).first()

            if not existing:
                new_mem = UserMemory(
                    user_id=user_id,
                    category=_safe_str(item.get("category"), 50) or "Personal",
                    key=key,
                    value=value,
                    memory=f"{key}: {value}",
                    confidence_score=_safe_confidence(item.get("confidence_score"), 1.0),
                    is_pinned=_as_bool(item.get("is_pinned", False))
                )

                db.session.add(new_mem)
                count += 1

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Memory import error: {e}")

        return jsonify({
            "error": "Failed to import memories due to a server error."
        }), 500

    return jsonify({
        "message": f"Successfully imported {count} memories."
    }), 200
