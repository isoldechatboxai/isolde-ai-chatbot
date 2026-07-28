from flask import Blueprint, jsonify, request
from google.genai.errors import ClientError
from app.extensions import db
# 🌟 FIX: Added Feedback, Broadcast, Setting imports
from app.models.user import User, Chat, Setting, Feedback, Broadcast
from app.services.gemini_service import generate_reply

admin_bp = Blueprint('admin_bp', __name__)

# ==========================================
# 1. REAL DATABASE ROUTE: User Management
# ==========================================
@admin_bp.route('/admin/users', methods=['GET', 'POST'], strict_slashes=False)
def manage_users():
    if request.method == 'GET':
        try:
            users = User.query.all()
            return jsonify({
                "status": "success",
                "users": [user.to_dict() for user in users]
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            new_user = User(
                name=data.get('username', 'Unknown'),
                email=data.get('email', ''),
                role="Client",
                status="Active"
            )
            new_user.set_password("isolde123")
            
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "User created perfectly!"}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/admin/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found!"}), 404
        
        data = request.get_json() or {}
        
        if 'username' in data:
            user.name = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'role' in data:
            user.role = data['role']
        if 'status' in data:
            user.status = data['status']
            
        db.session.commit()
        return jsonify({"status": "success", "message": "User updated successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/admin/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            return jsonify({"status": "success", "message": "User deleted!"}), 200
        return jsonify({"status": "error", "message": "User not found!"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 2. REAL DATABASE ROUTE: Chat Management
# ==========================================
@admin_bp.route('/admin/chats', methods=['GET', 'POST'], strict_slashes=False)
def manage_chats():
    if request.method == 'GET':
        try:
            chats = Chat.query.order_by(Chat.timestamp.desc()).all()
            return jsonify({
                "status": "success", 
                "chats": [chat.to_dict() for chat in chats]
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            user_message = data.get('user_message', '') or data.get('message', '')
            
            if not user_message:
                user_message = "Hello"

            ai_reply = ""
            
            try:
                ai_reply = generate_reply(prompt=user_message)
            
            except ClientError as e:
                error_text = str(e)
                if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
                    ai_reply = (
                        "⚠ Gemini quota exceeded. "
                        "Please try again later or upgrade your Gemini API quota."
                    )
                else:
                    ai_reply = f"⚠ Gemini Error: {error_text}"
            
            except Exception as e:
                ai_reply = f"⚠ Unexpected Error: {e}"

            new_chat = Chat(user_message=user_message, ai_response=ai_reply)
            db.session.add(new_chat)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "user_message": user_message,
                "ai_response": ai_reply,
                "chat_id": new_chat.id
            }), 200

        except Exception as e:
            import traceback
            print("\n" + "="*50)
            print("🚨 FULL ERROR TRACEBACK 🚨")
            traceback.print_exc()
            print("="*50 + "\n")
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/admin/chats/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    try:
        chat = Chat.query.get(chat_id)
        if chat:
            db.session.delete(chat)
            db.session.commit()
            return jsonify({"status": "success", "message": "Chat deleted"}), 200
        return jsonify({"status": "error", "message": "Chat not found!"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 3. SETTINGS ROUTES (Dynamic DB Integration)
# ==========================================
@admin_bp.route('/admin/settings', methods=['GET', 'POST'], strict_slashes=False)
def manage_settings():
    if request.method == 'GET':
        try:
            # 🌟 FIX: Fetch ALL settings to show in Admin Panel UI
            settings = Setting.query.all()
            settings_dict = {s.key: s.value for s in settings}
            
            settings_data = {
                "api_key_configured": bool(settings_dict.get("gemini_api_key")), 
                "model": settings_dict.get("gemini_model", "gemini-2.0-flash"),
                "system_prompt": settings_dict.get("system_prompt", ""),
                "maintenance_mode": settings_dict.get("maintenance_mode", "False")
            }
            return jsonify({"status": "success", "settings": settings_data}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            
            # 🌟 FIX: Dynamically update API Key, Prompt, and Maintenance Mode
            updates = {
                "gemini_api_key": data.get('api_key') or data.get('gemini_api_key'),
                "gemini_model": data.get('model'),
                "system_prompt": data.get('system_prompt'),
                "maintenance_mode": str(data.get('maintenance_mode')) if 'maintenance_mode' in data else None
            }
            
            for key, value in updates.items():
                if value is not None: # Update only if data is sent
                    setting = Setting.query.filter_by(key=key).first()
                    if not setting:
                        setting = Setting(key=key, value=str(value))
                        db.session.add(setting)
                    else:
                        setting.value = str(value)
                        
            db.session.commit()
            return jsonify({"status": "success", "message": "Settings perfectly updated in Database!"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/admin/settings/test-key', methods=['GET'])
def test_api_key():
    # 🌟 FIX: Check if Key actually exists in DB instead of fake success
    key_setting = Setting.query.filter_by(key="gemini_api_key").first()
    if key_setting and key_setting.value:
        return jsonify({"status": "success", "message": "API Key is Active and Configured!"}), 200
    return jsonify({"status": "error", "message": "No API Key found. Please add one."}), 400


# ==========================================
# 4. 🌟 NEW: BROADCAST & FEEDBACK ROUTES
# ==========================================
@admin_bp.route('/admin/broadcast', methods=['POST'])
def create_broadcast():
    try:
        data = request.get_json() or {}
        message = data.get('message')
        
        if not message:
            return jsonify({"status": "error", "message": "Message is required"}), 400
            
        new_broadcast = Broadcast(message=message)
        db.session.add(new_broadcast)
        db.session.commit()
        
        return jsonify({"status": "success", "message": "Broadcast sent to all Live Users!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/admin/feedbacks', methods=['GET'])
def get_feedbacks():
    try:
        feedbacks = Feedback.query.order_by(Feedback.timestamp.desc()).all()
        return jsonify({
            "status": "success", 
            "feedbacks": [fb.to_dict() for fb in feedbacks]
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500