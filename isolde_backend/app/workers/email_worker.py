# app/workers/email_worker.py

import time
import threading
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
    with smtplib.SMTP(smtp_config['MAIL_SERVER'], smtp_config['MAIL_PORT']) as server:
        if smtp_config.get('MAIL_USE_TLS'):
            server.starttls()
            
        username = smtp_config.get('MAIL_USERNAME')
        password = smtp_config.get('MAIL_PASSWORD')
        
        if username and password:
            server.login(username, password)
            
        server.send_message(msg)

def start_email_worker(app, subject: str, recipient: str, body: str, html_body: str = None):
    """
    Kicks off the long-running email process in a background thread.
    """
    def background_task():
        with app.app_context():
            app.logger.info(f"[WORKER START] Sending email to: {recipient}")
            try:
                # Fetching SMTP settings securely from Flask Config (.env)
                smtp_config = {
                    'MAIL_SERVER': app.config.get('MAIL_SERVER', 'smtp.gmail.com'),
                    'MAIL_PORT': app.config.get('MAIL_PORT', 587),
                    'MAIL_USE_TLS': app.config.get('MAIL_USE_TLS', True),
                    'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
                    'MAIL_PASSWORD': app.config.get('MAIL_PASSWORD'),
                    'MAIL_DEFAULT_SENDER': app.config.get('MAIL_DEFAULT_SENDER', 'admin@isolde.ai')
                }
                
                # 🛑 SAFETY CHECK: If passwords aren't set yet, just mock the email sending to avoid server crashes
                if not smtp_config['MAIL_USERNAME']:
                    app.logger.warning(f"[EMAIL MOCK] No SMTP credentials configured. Mocking email send to {recipient}")
                    time.sleep(1.5) # Simulate network delay
                else:
                    _send_email_task(subject, recipient, body, html_body, smtp_config)
                    
                app.logger.info(f"[WORKER SUCCESS] Email processing completed for: {recipient}")
                
            except Exception as e:
                app.logger.error(f"[WORKER FAILED] Email task failed for {recipient} after retries. Error: {str(e)}")

    # Initialize and start a daemon thread
    thread = threading.Thread(target=background_task)
    thread.daemon = True
    thread.start()