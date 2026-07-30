# app/middleware/request_logger.py

import time
import uuid
from flask import request, g, current_app

def setup_request_logger(app):
    """
    Middleware to log incoming requests and outgoing responses.
    Calculates execution time and assigns a unique Request ID for tracing.
    """
    
    @app.before_request
    def start_request_timer():
        # Assign a unique Request ID (uses existing header if provided by client)
        g.request_id = request.headers.get('X-Request-Id', str(uuid.uuid4()))
        # Start the execution timer
        g.start_time = time.time()

    @app.after_request
    def log_response_info(response):
        # Skip logging for CORS preflight requests to avoid log spam
        if request.method == 'OPTIONS':
            return response

        # Calculate total execution duration
        process_time = time.time() - getattr(g, 'start_time', time.time())

        # Extract essential request/response parameters
        client_ip = request.remote_addr
        method = request.method
        path = request.path
        status = response.status_code

        # Format the log entry
        log_message = (
            f"ReqID: {getattr(g, 'request_id', 'N/A')} | "
            f"Method: {method} | Path: {path} | "
            f"Status: {status} | IP: {client_ip} | "
            f"Duration: {process_time:.4f}s"
        )

        # Route log level based on standard HTTP status codes
        if status >= 500:
            current_app.logger.error(log_message)
        elif status >= 400:
            current_app.logger.warning(log_message)
        else:
            current_app.logger.info(log_message)

        # Inject the unique Request ID into the outgoing response headers
        response.headers['X-Request-Id'] = getattr(g, 'request_id', '')

        return response