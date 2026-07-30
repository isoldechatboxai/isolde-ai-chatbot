# app/middleware/security_headers.py

from flask import request

def setup_security_headers(app):
    """
    Middleware to inject standard security headers into all HTTP responses.
    This helps mitigate common web vulnerabilities like XSS, Clickjacking, and MIME-sniffing.
    """
    
    @app.after_request
    def add_security_headers(response):
        # Skip for OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return response

        # Prevents browsers from MIME-sniffing a response away from the declared content-type
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Enables cross-site scripting (XSS) filter built into most recent web browsers
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Prevents the page from being displayed in a frame (Clickjacking protection)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Enforces secure (HTTP over SSL/TLS) connections to the server
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Controls how much referrer information should be included with requests
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        return response