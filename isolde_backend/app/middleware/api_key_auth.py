# app/middleware/api_key_auth.py

from functools import wraps
from flask import request, jsonify, g, current_app
from app.services.api_key_service import verify_api_key

def require_api_key(required_permission=None):
    """
    Decorator/Middleware to protect routes using developer API Keys.
    Supports keys passed via 'X-API-Key' header or 'Authorization: Bearer isk_...'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = None

            # 1. Check 'X-API-Key' header
            if 'X-API-Key' in request.headers:
                api_key = request.headers['X-API-Key']
            
            # 2. Check 'Authorization: Bearer <key>' header
            elif 'Authorization' in request.headers:
                auth_header = request.headers['Authorization']
                if auth_header.startswith('Bearer '):
                    api_key = auth_header.split(' ')[1]

            if not api_key:
                return jsonify({
                    "error": "Unauthorized", 
                    "message": "Missing API Key. Provide 'X-API-Key' header or 'Authorization: Bearer <key>'."
                }), 401

            # 3. Verify the key securely via the service layer
            key_record = verify_api_key(api_key)
            if not key_record:
                current_app.logger.warning(f"Invalid or expired API key access attempt from IP: {request.remote_addr}")
                return jsonify({
                    "error": "Unauthorized", 
                    "message": "Invalid, revoked, or expired API key."
                }), 401

            # 4. Role-Based Access Control (RBAC) permission check
            if required_permission:
                permissions = [p.strip() for p in key_record.permissions.split(',')]
                if required_permission not in permissions and 'admin' not in permissions:
                    return jsonify({
                        "error": "Forbidden", 
                        "message": f"API key lacks required permission: '{required_permission}'"
                    }), 403

            # 5. Attach verified key and user identity to Flask global context 'g'
            g.api_key = key_record
            g.current_user_id = key_record.user_id

            return f(*args, **kwargs)
        return decorated_function
    return decorator