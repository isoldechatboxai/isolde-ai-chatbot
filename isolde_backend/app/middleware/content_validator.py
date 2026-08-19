# app/middleware/content_validator.py

from flask import request, jsonify

def setup_content_validator(app):
    """
    Middleware to ensure that incoming POST/PUT/PATCH requests
    with an actual payload have the correct 'application/json' Content-Type.

    Empty-body requests are allowed so protected endpoints can reach the
    authentication layer and return the appropriate 401 response instead of
    being rejected as invalid content before auth runs.
    """

    @app.before_request
    def validate_content_type():
        # Check only for methods that carry a data payload
        if request.method in ['POST', 'PUT', 'PATCH']:
            # Skip if it's a file upload route (they use multipart/form-data)
            if 'upload' in request.path or 'file' in request.path:
                return None

            # Requests without a body are valid for endpoints such as install/execute
            # that do not parse JSON. Let JWT auth decide whether access is allowed.
            if request.content_length in (None, 0):
                return None

            # Check if the content type is JSON for actual payloads
            if not request.is_json:
                return jsonify({
                    "error": "Unsupported Media Type",
                    "message": "Content-Type must be 'application/json'"
                }), 415

            return None