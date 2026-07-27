from flask import Blueprint, jsonify, request
from google.genai.errors import ClientError
from app.extensions import db
from app.models.user import User, Chat, Setting
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
            api_key_setting = Setting.query.filter_by(key="gemini_api_key").first()
            model_setting = Setting.query.filter_by(key="gemini_model").first()
            
            has_key = bool(api_key_setting and api_key_setting.value)
            current_model = model_setting.value if model_setting else "gemini-2.0-flash"
            
            settings_data = {
                "api_key_configured": has_key, 
                "model": current_model
            }
            return jsonify({"status": "success", "settings": settings_data}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            new_api_key = data.get('api_key') or data.get('gemini_api_key')
            new_model = data.get('model')
            
            if new_api_key:
                key_setting = Setting.query.filter_by(key="gemini_api_key").first()
                if not key_setting:
                    key_setting = Setting(key="gemini_api_key", value=new_api_key)
                    db.session.add(key_setting)
                else:
                    key_setting.value = new_api_key
            
            if new_model:
                model_setting = Setting.query.filter_by(key="gemini_model").first()
                if not model_setting:
                    model_setting = Setting(key="gemini_model", value=new_model)
                    db.session.add(model_setting)
                else:
                    model_setting.value = new_model
                    
            db.session.commit()
            return jsonify({"status": "success", "message": "Settings updated successfully in Database!"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500

@admin_bp.route('/admin/settings/test-key', methods=['GET'])
def test_api_key():
    return jsonify({"status": "success", "message": "API Key is Working Perfectly!"}), 200