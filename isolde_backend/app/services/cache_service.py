# app/services/cache_service.py

import time
import hashlib
from typing import Optional, Any
from flask import current_app

class ResponseCache:
    """
    In-memory TTL (Time-To-Live) cache for LLM responses and expensive computations.
    Reduces redundant API calls, lowers token costs, and drastically improves latency.
    """
    
    def __init__(self, default_ttl: int = 3600):
        # Storage structure: { cache_key: { "data": value, "expires_at": timestamp } }
        self._store = {}
        self.default_ttl = default_ttl  # Default TTL: 1 hour

    def _generate_key(self, prefix: str, identifier: str) -> str:
        """Generates a secure SHA-256 hash key for storage lookup."""
        raw_string = f"{prefix}:{identifier}"
        return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

    def get(self, prefix: str, identifier: str) -> Optional[Any]:
        """Retrieves cached data if it exists and has not expired."""
        cache_key = self._generate_key(prefix, identifier)
        
        if cache_key not in self._store:
            return None

        cached_item = self._store[cache_key]
        
        # Check if expired
        if time.time() > cached_item["expires_at"]:
            del self._store[cache_key]
            return None

        if current_app:
            current_app.logger.info(f"[Cache HIT] Retrieved key for prefix: {prefix}")
            
        return cached_item["data"]

    def set(self, prefix: str, identifier: str, data: Any, ttl: Optional[int] = None) -> None:
        """Stores data in cache with an expiration timestamp."""
        cache_key = self._generate_key(prefix, identifier)
        expiration_time = time.time() + (ttl if ttl is not None else self.default_ttl)

        self._store[cache_key] = {
            "data": data,
            "expires_at": expiration_time
        }

        if current_app:
            current_app.logger.info(f"[Cache SET] Stored key for prefix: {prefix}")

    def clear(self) -> None:
        """Clears the entire cache store."""
        self._store.clear()
        if current_app:
            current_app.logger.info("[Cache CLEAR] Cache store wiped successfully.")

# Singleton instance for application-wide use
cache_service = ResponseCache()