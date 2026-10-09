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
            # Apple's signed authorization response uses form_post. State,
            # nonce and identity verification remain in the OAuth callback.
            if (request.endpoint == "auth.oauth_callback"
                    and (request.view_args or {}).get("provider") == "apple"
                    and request.mimetype == "application/x-www-form-urlencoded"):
                return None
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

            # These blueprints already validate payload shape and expose
            # established, distinct error contracts used by existing clients.
            if (request.blueprint not in {"auth", "public_api_bp", "unified_engine_bp"}
                    and not isinstance(request.get_json(silent=True), dict)):
                return jsonify({"error": "Request body must be a JSON object."}), 400

            return None
