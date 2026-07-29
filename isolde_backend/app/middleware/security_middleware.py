# app/middleware/security_middleware.py
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def enterprise_security_guard(required_role="User"):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
                claims = get_jwt()
                if required_role == "Admin" and not claims.get("is_admin", False):
                    return jsonify({"error": "Forbidden: Admin privileges required."}), 403
                return fn(*args, **kwargs)
            except Exception as e:
                return jsonify({"error": f"Security Validation Failed: {str(e)}"}), 401
        return wrapper
    return decorator