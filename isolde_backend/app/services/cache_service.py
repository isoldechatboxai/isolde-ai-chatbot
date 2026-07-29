# app/services/cache_service.py
import redis
import json
from flask import current_app

class RedisCacheService:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    def get_cached_response(self, cache_key: str):
        val = self.redis_client.get(cache_key)
        return json.loads(val) if val else None

    def set_cached_response(self, cache_key: str, data: dict, expire_seconds: int = 3600):
        self.redis_client.setex(cache_key, expire_seconds, json.dumps(data))