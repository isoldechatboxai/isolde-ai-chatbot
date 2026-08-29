# app/workers/email_worker.py

import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def with_retry(max_retries=3, initial_delay=2, backoff_factor=2):
    """
    Decorator to automatically retry a failed task.
    Implements exponential backoff (e.g., waits 2s, then 4s, then 8s).
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

@with_retry(max_retries=3, initial_delay=2)
def _send_email_task(subject: str, recipient: str, body: str, html_body: str, smtp_config: dict):
    """
    Core logic to connect to SMTP server and send an email.
    No route/Flask request logic here.
    """
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_config.get('MAIL_DEFAULT_SENDER', 'noreply@isolde.ai')
    msg['To'] = recipient

    # Attach plain text and HTML versions
    msg.attach(MIMEText(body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    # Connect to Mail Server and Send
    with smtplib.SMTP(
        smtp_config['MAIL_SERVER'], smtp_config['MAIL_PORT'],
        timeout=smtp_config.get('MAIL_TIMEOUT_SECONDS', 10),
    ) as server:
        if smtp_config.get('MAIL_USE_TLS'):
            server.starttls()
            
        username = smtp_config.get('MAIL_USERNAME')
        password = smtp_config.get('MAIL_PASSWORD')
        
        if username and password:
            server.login(username, password)
            
        server.send_message(msg)

def start_email_worker(app, subject: str, recipient: str, body: str, html_body: str = None):
    """
    Deliver an authentication email synchronously with bounded retries.

    In-process daemon threads can be terminated during worker recycling and
    silently lose verification/reset messages. Callers receive a truthful
    success value and can surface delivery failure without exposing details.
    """
    with app.app_context():
        smtp_config = {
            'MAIL_SERVER': app.config.get('MAIL_SERVER'),
            'MAIL_PORT': app.config.get('MAIL_PORT', 587),
            'MAIL_USE_TLS': app.config.get('MAIL_USE_TLS', True),
            'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
            'MAIL_PASSWORD': app.config.get('MAIL_PASSWORD'),
            'MAIL_DEFAULT_SENDER': app.config.get('MAIL_DEFAULT_SENDER'),
            'MAIL_TIMEOUT_SECONDS': app.config.get('MAIL_TIMEOUT_SECONDS', 10),
        }
        if not all((smtp_config['MAIL_SERVER'], smtp_config['MAIL_USERNAME'],
                    smtp_config['MAIL_PASSWORD'], smtp_config['MAIL_DEFAULT_SENDER'])):
            app.logger.error("Authentication email delivery is not configured.")
            return False
        try:
            _send_email_task(subject, recipient, body, html_body, smtp_config)
            app.logger.info("Authentication email delivered.")
            return True
        except Exception:
            app.logger.exception("Authentication email delivery failed after bounded retries.")
            return False
