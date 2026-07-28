# app/routes/memory_routes.py
from flask import Blueprint, request, jsonify
from app import db
from app.models.memory_model import UserMemory

memory_bp = Blueprint('memory_bp', __name__)

@memory_bp.route('/memory/save', methods=['POST'])
def save_memory():
    data = request.get_json() or {}
    memory_text = data.get('memory', '').strip()
    category = data.get('category', 'Other')
    user_id = data.get('user_id', 'guest_user')

    if not memory_text:
        return jsonify({"error": "Memory content cannot be empty"}), 400

    existing_memories = UserMemory.query.filter_by(user_id=user_id).all()
    for mem in existing_memories:
        if mem.memory.lower() == memory_text.lower():
            return jsonify({"message": "Memory already exists", "memory": mem.to_dict()}), 200
        if any(word in mem.memory.lower() for word in memory_text.lower().split() if len(word) > 4):
            mem.memory = memory_text
            mem.category = category
            db.session.commit()
            return jsonify({"message": "Memory updated successfully", "memory": mem.to_dict()}), 200

    new_memory = UserMemory(user_id=user_id, memory=memory_text, category=category)
    db.session.add(new_memory)
    db.session.commit()

    return jsonify({"message": "Memory saved successfully", "memory": new_memory.to_dict()}), 201

@memory_bp.route('/memory/list', methods=['GET'])
def list_memories():
    memories = UserMemory.query.order_by(UserMemory.updated_at.desc()).all()
    return jsonify({"memories": [m.to_dict() for m in memories]}), 200

@memory_bp.route('/memory/<int:memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    memory = UserMemory.query.get(memory_id)
    if not memory:
        return jsonify({"error": "Memory not found"}), 404

    db.session.delete(memory)
    db.session.commit()
    return jsonify({"message": "Memory deleted successfully"}), 200

@memory_bp.route('/memory/all', methods=['DELETE'])
def clear_all_memories():
    UserMemory.query.delete()
    db.session.commit()
    return jsonify({"message": "All memories cleared successfully"}), 200