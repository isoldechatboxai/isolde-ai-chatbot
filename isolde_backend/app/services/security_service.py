import hashlib
import secrets

class SecurityService:
    """
    Enterprise security service handling cryptographic hashing, 
    API key generation, and secure payload verification.
    """
    @staticmethod
    def generate_secure_api_key() -> tuple[str, str]:
        """
        Generates a secure random API key and its corresponding SHA-256 hash for secure storage.
        Returns: (raw_key, hashed_key)
        """
        raw_key = f"isolde_{secrets.token_hex(32)}"
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, hashed_key

    @staticmethod
    def verify_api_key(raw_key: str, stored_hash: str) -> bool:
        """
        Safely verifies a plain-text API key against a stored SHA-256 hash.
        """
        computed_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        return secrets.compare_digest(computed_hash, stored_hash)