# app/services/security_service.py

import base64
import hashlib
import hmac
import html
import re
from typing import Optional
from cryptography.fernet import Fernet
from flask import current_app

class SecurityService:
    """
    Production hardening security service responsible for cryptographic encryption,
    decryption, data sanitization, and signature verification.
    """

    def __init__(self, secret_key: Optional[str] = None):
        # Derive a stable Fernet encryption key from application secret or default fallback
        key_material = secret_key or "isolde_production_hardening_secure_salt_key_32bytes"
        digest = hashlib.sha256(key_material.encode()).digest()
        self._fernet_key = base64.urlsafe_b64encode(digest)
        self._cipher = Fernet(self._fernet_key)

    def encrypt_data(self, plaintext: str) -> str:
        """Encrypts sensitive plaintext data securely using symmetric cryptography."""
        if not plaintext:
            return ""
        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[SecurityService] Encryption error: {str(e)}")
            raise ValueError("Failed to encrypt sensitive data.")

    def decrypt_data(self, ciphertext: str) -> str:
        """Decrypts encrypted ciphertext back to plaintext."""
        if not ciphertext:
            return ""
        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[SecurityService] Decryption error: {str(e)}")
            raise ValueError("Failed to decrypt ciphertext.")

    def sanitize_input(self, raw_text: str) -> str:
        """Sanitizes user input to prevent Cross-Site Scripting (XSS) and injection vulnerabilities."""
        if not raw_text:
            return ""
        # Escape HTML entities
        escaped = html.escape(raw_text)
        # Strip potential null bytes or control injection sequences
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', escaped)
        return sanitized.strip()

    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verifies HMAC SHA-256 signatures for webhook and API security validation."""
        if not payload or not signature or not secret:
            return False
        computed_sig = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed_sig, signature)

# Singleton instance for application-wide use
security_service = SecurityService()