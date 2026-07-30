# app/routes/memory_routes.py
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.memory_model import UserMemory
from app.services.provider_router import generate_reply
import json
import csv
import io

memory_bp = Blueprint('memory_bp', __name__)

def extract_memory_with_ai(raw_text):
    """
    Uses Universal AI wrapper to intelligently parse a statement into Category, Key, Value, and Confidence.
    Works seamlessly with Groq, Gemini, OpenAI, and Claude without crashing.
    """
    try:
        prompt = f"""
        Analyze the following user statement and extract memory information in strict JSON format.
        Categories allowed: Personal, Location, Education, Work, Preference, Goals, Health, Custom.
        Return ONLY a JSON object with keys: "category", "key", "value", "confidence".
        Statement: "{raw_text}"
        """
        # Universal wrapper handles whichever API key is active in Admin panel (Groq/Gemini/OpenAI)
        response_text = generate_reply(prompt, system_context="You are a precise JSON parser. Return strict JSON only.")
        text = response_text.strip()
        
        # Clean markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        
        data = json.loads(text)
        return {
            "category": data.get("category", "Personal"),
            "key": data.get("key", "General"),
            "value": data.get("value", raw_text),
            "confidence": float(data.get("confidence", 0.95))
        }
    except Exception:
        # Fallback if AI parsing fails
        return {"category": "Personal", "key": "General", "value": raw_text, "confidence": 0.85}

@memory_bp.route('/memory/save', methods=['POST'])
@jwt_required(optional=True)
def save_memory():
    data = request.get_json() or {}
    memory_text = data.get('memory', '').strip()
    user_id = get_jwt_identity() or data.get('user_id', 'guest_user')

    if not memory_text:
        return jsonify({"error": "Memory content cannot be empty"}), 400

    # Smart Extraction
    extracted = extract_memory_with_ai(memory_text)
    category = data.get('category', extracted["category"])
    key = data.get('key', extracted["key"])
    value = data.get('value', extracted["value"])
    confidence = data.get('confidence_score', extracted["confidence"])

    # Low confidence threshold check
    if confidence < 0.7:
        return jsonify({"message": "Memory confidence too low to save automatically", "confidence": confidence}), 200

    # Check for existing key to update (Versioning)
    existing = UserMemory.query.filter_by(user_id=user_id, key=key).first()
    if existing:
        if existing.value.lower() == value.lower():
            return jsonify({"message": "Memory already up-to-date", "memory": existing.to_dict()}), 200
        
        # Save old value to version history
        history = []
        try:
            if existing.version_history:
                history = json.loads(existing.version_history)
        except Exception:
            history = []
        
        history.append({"value": existing.value, "updated_at": existing.updated_at.isoformat() if existing.updated_at else ""})
        
        existing.version_history = json.dumps(history)
        existing.value = value
        existing.memory = f"{key}: {value}"
        existing.category = category
        existing.confidence_score = confidence
        db.session.commit()
        return jsonify({"message": "Memory updated with versioning", "memory": existing.to_dict()}), 200

    # Create new structured memory
    new_memory = UserMemory(
        user_id=user_id,
        category=category,
        key=key,
        value=value,
        memory=f"{key}: {value}" if key and value else memory_text,
        confidence_score=confidence,
        is_pinned=data.get('is_pinned', False)
    )
    db.session.add(new_memory)
    db.session.commit()

    return jsonify({"message": "Structured memory saved successfully", "memory": new_memory.to_dict()}), 201

@memory_bp.route('/memory/list', methods=['GET'])
@jwt_required(optional=True)
def list_memories():
    user_id = get_jwt_identity()
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()

    query = UserMemory.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    # NEW: optional category filter (?category=Personal). "All" or empty = no filter.
    if category_filter and category_filter.lower() != 'all':
        if category_filter.lower() == 'uncategorized':
            query = query.filter((UserMemory.category == None) | (UserMemory.category == ''))
        else:
            query = query.filter(UserMemory.category == category_filter)

    if search_query:
        query = query.filter(
            (UserMemory.key.ilike(f"%{search_query}%")) |
            (UserMemory.value.ilike(f"%{search_query}%")) |
            (UserMemory.category.ilike(f"%{search_query}%")) |
            (UserMemory.memory.ilike(f"%{search_query}%"))
        )

    memories = query.order_by(UserMemory.is_pinned.desc(), UserMemory.updated_at.desc()).all()
    return jsonify({"memories": [m.to_dict() for m in memories]}), 200

@memory_bp.route('/memory/categories', methods=['GET'])
@jwt_required(optional=True)
def get_memory_categories():
    """
    Returns distinct categories that actually exist for this user's memories, with counts.
    Used by the frontend to render dynamic filter tabs (no hardcoded category list needed,
    since the AI extractor can produce Personal, Location, Education, Work, Preference,
    Goals, Health, Custom, or anything else).
    """
    try:
        user_id = get_jwt_identity()
        query = db.session.query(UserMemory.category, db.func.count(UserMemory.id))
        if user_id:
            query = query.filter(UserMemory.user_id == user_id)

        rows = query.group_by(UserMemory.category).all()

        counts = {}
        for cat, count in rows:
            label = cat if cat else "Uncategorized"
            counts[label] = counts.get(label, 0) + count

        total = sum(counts.values())

        return jsonify({
            "total": total,
            "categories": counts  # e.g. {"Personal": 4, "Work": 2, "Health": 1}
        }), 200

    except Exception as e:
        return jsonify({"error": "Failed to fetch categories", "details": str(e)}), 500

@memory_bp.route('/memory/stats', methods=['GET'])
@jwt_required(optional=True)
def memory_stats():
    user_id = get_jwt_identity()
    query = UserMemory.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    memories = query.all()
    total = len(memories)
    pinned = sum(1 for m in memories if m.is_pinned)
    categories = len(set(m.category for m in memories))
    last_updated = max((m.updated_at for m in memories), default=None)

    return jsonify({
        "total_memories": total,
        "pinned_memories": pinned,
        "total_categories": categories,
        "last_updated": last_updated.isoformat() if last_updated else None
    }), 200

@memory_bp.route('/memory/<int:memory_id>/pin', methods=['PATCH'])
@jwt_required(optional=True)
def toggle_pin_memory(memory_id):
    memory = UserMemory.query.get(memory_id)
    if not memory:
        return jsonify({"error": "Memory not found"}), 404
    
    memory.is_pinned = not memory.is_pinned
    db.session.commit()
    return jsonify({"message": "Pin status updated", "memory": memory.to_dict()}), 200

@memory_bp.route('/memory/<int:memory_id>', methods=['DELETE'])
@jwt_required(optional=True)
def delete_memory(memory_id):
    memory = UserMemory.query.get(memory_id)
    if not memory:
        return jsonify({"error": "Memory not found"}), 404

    db.session.delete(memory)
    db.session.commit()
    return jsonify({"message": "Memory deleted successfully"}), 200

@memory_bp.route('/memory/category/<string:category_name>', methods=['DELETE'])
@jwt_required(optional=True)
def delete_category(category_name):
    user_id = get_jwt_identity()
    query = UserMemory.query.filter_by(category=category_name)
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    query.delete()
    db.session.commit()
    return jsonify({"message": f"Category {category_name} cleared successfully"}), 200

@memory_bp.route('/memory/all', methods=['DELETE'])
@jwt_required(optional=True)
def clear_all_memories():
    user_id = get_jwt_identity()
    query = UserMemory.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    query.delete()
    db.session.commit()
    return jsonify({"message": "All memories cleared successfully"}), 200

@memory_bp.route('/memory/export/<string:file_format>', methods=['GET'])
@jwt_required(optional=True)
def export_memories(file_format):
    user_id = get_jwt_identity()
    query = UserMemory.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    memories = query.all()
    data = [m.to_dict() for m in memories]

    if file_format.lower() == 'json':
        return jsonify({"memories": data}), 200
    elif file_format.lower() == 'csv':
        si = io.StringIO()
        writer = csv.DictWriter(si, fieldnames=["id", "category", "key", "value", "confidence_score", "is_pinned", "updated_at"])
        writer.writeheader()
        for row in data:
            writer.writerow({k: row.get(k) for k in ["id", "category", "key", "value", "confidence_score", "is_pinned", "updated_at"]})
        output = si.getvalue()
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=memories.csv"})
    
    return jsonify({"error": "Invalid format. Use json or csv."}), 400

@memory_bp.route('/memory/import', methods=['POST'])
@jwt_required(optional=True)
def import_memories():
    user_id = get_jwt_identity() or 'guest_user'
    data = request.get_json() or {}
    mem_list = data.get('memories', [])

    count = 0
    for item in mem_list:
        key = item.get('key')
        value = item.get('value')
        if not key or not value:
            continue
        
        existing = UserMemory.query.filter_by(user_id=user_id, key=key).first()
        if not existing:
            new_mem = UserMemory(
                user_id=user_id,
                category=item.get('category', 'Personal'),
                key=key,
                value=value,
                memory=f"{key}: {value}",
                confidence_score=item.get('confidence_score', 1.0),
                is_pinned=item.get('is_pinned', False)
            )
            db.session.add(new_mem)
            count += 1
    db.session.commit()
    return jsonify({"message": f"Successfully imported {count} memories."}), 200