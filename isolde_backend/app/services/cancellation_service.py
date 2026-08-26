import json
import threading
import time

from flask import current_app


class CancellationStoreUnavailable(RuntimeError):
    pass


class CancellationStore:
    def __init__(self):
        self._memory = {}
        self._lock = threading.Lock()
        self._redis_clients = {}

    def _redis(self):
        url = current_app.config.get("CANCELLATION_REDIS_URL", "").strip()
        if not url:
            return None
        if url not in self._redis_clients:
            try:
                import redis
                self._redis_clients[url] = redis.Redis.from_url(
                    url, decode_responses=True,
                    socket_connect_timeout=current_app.config.get("REDIS_CONNECT_TIMEOUT_SECONDS", 2),
                    socket_timeout=current_app.config.get("REDIS_SOCKET_TIMEOUT_SECONDS", 2),
                )
            except Exception as error:
                raise CancellationStoreUnavailable("Cancellation storage is unavailable.") from error
        return self._redis_clients[url]

    @staticmethod
    def _key(generation_id):
        return f"isolde:generation:{generation_id}"

    def register(self, generation_id, owner, conversation_id=None):
        ttl = int(current_app.config.get("CANCELLATION_TTL_SECONDS", 900))
        payload = json.dumps({"owner": owner, "conversation_id": str(conversation_id or ""), "cancelled": False})
        client = self._redis()
        if client is not None:
            try:
                if not client.set(self._key(generation_id), payload, ex=ttl, nx=True):
                    raise ValueError("Generation ID is already registered.")
                return
            except ValueError:
                raise
            except Exception as error:
                raise CancellationStoreUnavailable("Cancellation storage is unavailable.") from error
        expires = time.monotonic() + ttl
        with self._lock:
            self._purge_memory()
            if generation_id in self._memory:
                raise ValueError("Generation ID is already registered.")
            self._memory[generation_id] = {"owner": owner, "conversation_id": str(conversation_id or ""), "cancelled": False, "expires": expires}

    def cancel(self, generation_id, owner):
        client = self._redis()
        if client is not None:
            script = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local value = cjson.decode(raw)
if value.owner ~= ARGV[1] then return -1 end
value.cancelled = true
redis.call('SET', KEYS[1], cjson.encode(value), 'EX', ARGV[2])
return 1
"""
            try:
                return int(client.eval(script, 1, self._key(generation_id), owner, int(current_app.config.get("CANCELLATION_TTL_SECONDS", 900))))
            except Exception as error:
                raise CancellationStoreUnavailable("Cancellation storage is unavailable.") from error
        with self._lock:
            self._purge_memory()
            value = self._memory.get(generation_id)
            if value is None:
                return 0
            if value["owner"] != owner:
                return -1
            value["cancelled"] = True
            return 1

    def is_cancelled(self, generation_id, owner):
        client = self._redis()
        try:
            raw = client.get(self._key(generation_id)) if client is not None else None
        except Exception as error:
            raise CancellationStoreUnavailable("Cancellation storage is unavailable.") from error
        if client is not None:
            if not raw:
                return False
            value = json.loads(raw)
            return value.get("owner") == owner and value.get("cancelled") is True
        with self._lock:
            self._purge_memory()
            value = self._memory.get(generation_id)
            return bool(value and value["owner"] == owner and value["cancelled"])

    def unregister(self, generation_id, owner):
        client = self._redis()
        if client is not None:
            script = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
if cjson.decode(raw).owner ~= ARGV[1] then return -1 end
return redis.call('DEL', KEYS[1])
"""
            try:
                return int(client.eval(script, 1, self._key(generation_id), owner))
            except Exception as error:
                raise CancellationStoreUnavailable("Cancellation storage is unavailable.") from error
        with self._lock:
            value = self._memory.get(generation_id)
            if value and value["owner"] == owner:
                del self._memory[generation_id]
                return 1
            return -1 if value else 0

    def _purge_memory(self):
        now = time.monotonic()
        for key in [key for key, value in self._memory.items() if value["expires"] <= now]:
            del self._memory[key]


cancellation_store = CancellationStore()
