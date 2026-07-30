# app/middleware/rate_limit_middleware.py

import time
from functools import wraps
from flask import request, jsonify, g, current_app

# Simple in-memory token bucket/counter store (can be replaced with Redis in production)
# Structure: { key_id: { "window_start": timestamp, "count": request_count } }
_REQUEST_HISTORY = {}

def api_key_rate_limit(max_requests_per_minute=60):
    """
    Middleware/Decorator to enforce rate limiting per API Key.
    Prevents API abuse by capping requests within a rolling 60-second window.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure the request has passed through API key authentication first
            api_key_record = getattr(g, 'api_key', None)
            if not api_key_record:
                # If no API key is present, let other authentications handle it or bypass
                return f(*args, **kwargs)

            key_id = api_key_record.id
            current_time = time.time()
            window_size = 60  # 1 minute window

            # Initialize or clean up rate limit window for this key
            if key_id not in _REQUEST_HISTORY:
                _REQUEST_HISTORY[key_id] = {
                    "window_start": current_time,
                    "count": 0
                }

            history = _REQUEST_HISTORY[key_id]

            # Check if the time window has expired
            if current_time - history["window_start"] > window_size:
                history["window_start"] = current_time
                history["count"] = 0

            # Increment request count
            history["count"] += 1

            # Calculate remaining limit headers
            remaining = max(0, max_requests_per_minute - history["count"])

            if history["count"] > max_requests_per_minute:
                current_app.logger.warning(f"Rate limit exceeded for API Key ID: {key_id}")
                response = jsonify({
                    "error": "Rate Limit Exceeded",
                    "message": f"You have exceeded your rate limit of {max_requests_per_minute} requests per minute."
                })
                response.status_code = 429
                response.headers['X-RateLimit-Limit'] = str(max_requests_per_minute)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(int(history["window_start"] + window_size))
                return response

            # Execute the route function
            response = f(*args, **kwargs)
            
            # If response is a Flask Response object, inject rate limit headers
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(max_requests_per_minute)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(int(history["window_start"] + window_size))

            return response
        return decorated_function
    return decorator