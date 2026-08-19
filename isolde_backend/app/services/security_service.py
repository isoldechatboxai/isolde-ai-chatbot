import base64
import hashlib
import hmac
import html
import os
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
        """
        Derive a stable Fernet encryption key.

        Preferred order:
        1. Explicit secret_key argument
        2. Flask app config SECURITY_ENCRYPTION_KEY
        3. Flask app config SECRET_KEY
        4. Environment SECURITY_ENCRYPTION_KEY
        5. Environment SECRET_KEY
        6. Environment FLASK_SECRET_KEY

        In production, if no key material is available, fail immediately.
        In non-production environments, keep a development-only fallback.
        """
        key_material = secret_key

        if not key_material:
            try:
                key_material = (
                    current_app.config.get("SECURITY_ENCRYPTION_KEY")
                    or current_app.config.get("SECRET_KEY")
                )
            except RuntimeError:
                key_material = None

        if not key_material:
            key_material = (
                os.getenv("SECURITY_ENCRYPTION_KEY")
                or os.getenv("SECRET_KEY")
                or os.getenv("FLASK_SECRET_KEY")
            )

        if not key_material:
            environment = os.getenv(
                "FLASK_ENV",
                os.getenv("ENVIRONMENT", "development"),
            ).strip().lower()

            if environment in {"production", "prod"}:
                raise RuntimeError(
                    "SecurityService requires SECURITY_ENCRYPTION_KEY or SECRET_KEY in production."
                )

            # Development-only fallback.
            # This must not be used in production.
            key_material = "isolde-development-only-insecure-fallback"

        digest = hashlib.sha256(key_material.encode()).digest()
        self._fernet_key = base64.urlsafe_b64encode(digest)
        self._cipher = Fernet(self._fernet_key)

    def encrypt_data(self, plaintext: str) -> str:
        """
        Encrypts sensitive plaintext data securely using symmetric cryptography.
        """
        if not plaintext:
            return ""

        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode("utf-8"))
            return encrypted_bytes.decode("utf-8")
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[SecurityService] Encryption error: {str(e)}")
            raise ValueError("Failed to encrypt sensitive data.")

    def decrypt_data(self, ciphertext: str) -> str:
        """
        Decrypts encrypted ciphertext back to plaintext.
        """
        if not ciphertext:
            return ""

        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[SecurityService] Decryption error: {str(e)}")
            raise ValueError("Failed to decrypt ciphertext.")

    def sanitize_input(self, raw_text: str) -> str:
        """
        Sanitizes user input to prevent Cross-Site Scripting (XSS) and injection vulnerabilities.
        """
        if not raw_text:
            return ""

        escaped = html.escape(raw_text)
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", escaped)

        return sanitized.strip()

    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """
        Verifies HMAC SHA-256 signatures for webhook and API security validation.
        """
        if not payload or not signature or not secret:
            return False

        computed_sig = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_sig, signature)


# Singleton instance for application-wide use.
security_service = SecurityService()