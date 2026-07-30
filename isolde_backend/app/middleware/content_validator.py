# app/middleware/content_validator.py

from flask import request, jsonify

def setup_content_validator(app):
    """
    Middleware to ensure that incoming POST/PUT/PATCH requests 
    have the correct 'application/json' Content-Type.
    """
    
    @app.before_request
    def validate_content_type():
        # Check only for methods that carry a data payload
        if request.method in ['POST', 'PUT', 'PATCH']:
            # Skip if it's a file upload route (they use multipart/form-data)
            if 'upload' in request.path or 'file' in request.path:
                return None
                
            # Check if the content type is JSON
            if not request.is_json:
                return jsonify({
                    "error": "Unsupported Media Type", 
                    "message": "Content-Type must be 'application/json'"
                }), 415