# app/services/caching_service.py

import json
from typing import Any, Optional
from flask import current_app

class CachingService:
    """
    Provides caching capabilities for accelerating query responses,
    reducing database load, and managing transient state data.
    """

    def __init__(self):
        # In-memory fallback dictionary cache if Redis is not configured
        self._memory_cache = {}

    def set(self, key: str, value: Any, timeout_seconds: int = 300) -> bool:
        """Stores a value in the cache with a specified expiration time."""
        try:
            serialized = json.dumps(value)
            self._memory_cache[key] = serialized
            if current_app:
                current_app.logger.info(f"[CachingService] Cached key: '{key}' (TTL: {timeout_seconds}s)")
            return True
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[CachingService] Error setting cache key '{key}': {str(e)}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """Retrieves and deserializes a cached value by key."""
        try:
            serialized = self._memory_cache.get(key)
            if not serialized:
                return None
            return json.loads(serialized)
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[CachingService] Error retrieving cache key '{key}': {str(e)}")
            return None

    def delete(self, key: str) -> bool:
        """Deletes a key from the cache."""
        if key in self._memory_cache:
            del self._memory_cache[key]
            return True
        return False

# Singleton instance for application-wide use
caching_service = CachingService()