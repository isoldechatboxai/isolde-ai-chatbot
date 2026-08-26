"""
Universal AI Provider Router — Production-Grade Implementation.
Supported providers:
Google Gemini | OpenAI | Anthropic Claude | Groq
OpenRouter | DeepSeek | Mistral
Provider resolution order (deterministic):
1. "ai_provider" Setting row  →  explicit Admin-Panel selection
2. "gemini_api_key" prefix    →  legacy backward-compatible detection
3. Fallback to "gemini"
Features: automatic failover, circuit breaker, retry with exponential
backoff, request timeout, health-check cache, provider metrics,
streaming, connection pooling, centralized exception handling.
Backward-compatible public API (do NOT rename):
generate_reply()
generate_reply_stream()
embed_text()
analyze_image()
ProviderManager / ProviderResponse / get_provider_manager()
"""
import json
import time
import threading
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Generator, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import current_app
from app.models.user import Setting

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KNOWN_PROVIDERS = frozenset({
    "gemini", "openai", "claude", "groq",
    "openrouter", "deepseek", "mistral",
})

DEFAULT_PRIORITY: List[str] = []

DEFAULT_MODELS: Dict[str, str] = {
    "gemini": "gemini-3.7-flash",
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o",
    "claude": "claude-sonnet-4-20250514",
    "openrouter": "openai/gpt-4o",
    "deepseek": "deepseek-chat",
    "mistral": "mistral-large-latest",
}

MODEL_SETTING_KEYS: Dict[str, str] = {
    "gemini": "gemini_model",
    "groq": "groq_model",
    "openai": "openai_model",
    "claude": "claude_model",
    "openrouter": "openrouter_model",
    "deepseek": "deepseek_model",
    "mistral": "mistral_model",
}

API_KEY_SETTING_KEYS: Dict[str, str] = {
    "gemini": "gemini_api_key",
    "openai": "openai_api_key",
    "claude": "claude_api_key",
    "groq": "groq_api_key",
    "openrouter": "openrouter_api_key",
    "deepseek": "deepseek_api_key",
    "mistral": "mistral_api_key",
}

BASE_URL_SETTING_KEYS: Dict[str, str] = {
    "openai": "openai_base_url",
    "groq": "groq_base_url",
    "openrouter": "openrouter_base_url",
    "deepseek": "deepseek_base_url",
    "mistral": "mistral_base_url",
}

DEFAULT_BASE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
}

DEFAULT_TIMEOUT = 60          # seconds per provider call
MAX_RETRIES     = 3
BACKOFF_BASE    = 0.5         # seconds; doubles each retry

# ---------------------------------------------------------------------------
# Safe Logger (Flask context aware)
# ---------------------------------------------------------------------------
_fallback_logger = logging.getLogger(__name__)

def _get_logger():
    try:
        return current_app.logger
    except RuntimeError:
        return _fallback_logger

# ---------------------------------------------------------------------------
# Connection-pooled HTTP session (singleton, thread-safe)
# ---------------------------------------------------------------------------
_session_lock = threading.Lock()
_session: Optional[requests.Session] = None

def _get_http_session() -> requests.Session:
    """Return a module-level requests.Session with connection pooling."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                retry_strategy = Retry(
                    total=0,
                    connect=0,
                    read=0,
                    status=0,
                )
                adapter = HTTPAdapter(
                    max_retries=retry_strategy,
                    pool_connections=20,
                    pool_maxsize=20,
                )
                s.mount("https://", adapter)
                s.mount("http://", adapter)
                _session = s
    return _session

# ---------------------------------------------------------------------------
# Unified response object
# ---------------------------------------------------------------------------
@dataclass
class ProviderResponse:
    """Standardized response from any AI provider."""
    success: bool
    text: str = ""
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    tokens_used: Optional[int] = None
    error: str = ""
    raw: Any = None

# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------
class CircuitBreaker:
    """Per-provider circuit breaker."""
    STATE_CLOSED    = "closed"
    STATE_OPEN      = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.failure_count     = 0
        self.last_failure_time = 0.0
        self.state             = self.STATE_CLOSED
        self._lock             = threading.Lock()

    def record_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = self.STATE_CLOSED

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = self.STATE_OPEN

    def allow_request(self) -> bool:
        with self._lock:
            if self.state == self.STATE_CLOSED:
                return True
            if self.state == self.STATE_OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = self.STATE_HALF_OPEN
                    self.failure_count = 0  # Reset count for the probe phase
                    return True
                return False
            return True  # half_open: allow one probe

# ---------------------------------------------------------------------------
# Provider Metrics
# ---------------------------------------------------------------------------
class ProviderMetrics:
    """Track latency / success / failure per provider."""
    def __init__(self):
        self._lock  = threading.Lock()
        self._data: Dict[str, Dict[str, float]] = {}

    def record(self, provider: str, latency_ms: float, success: bool):
        with self._lock:
            if provider not in self._data:
                self._data[provider] = {
                    "total_requests":   0,
                    "success_count":    0,
                    "failure_count":    0,
                    "total_latency_ms": 0.0,
                }
            entry = self._data[provider]
            entry["total_requests"]   += 1
            entry["total_latency_ms"] += latency_ms
            if success:
                entry["success_count"] += 1
            else:
                entry["failure_count"] += 1

    def get(self, provider: str) -> Dict[str, float]:
        with self._lock:
            return dict(self._data.get(provider, {}))

    def get_all(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            return {k: dict(v) for k, v in self._data.items()}

# ---------------------------------------------------------------------------
# Health Check Cache
# ---------------------------------------------------------------------------
class HealthCheckCache:
    """Cache provider availability so we skip known-down providers quickly."""
    def __init__(self, ttl: float = 120.0):
        self.ttl      = ttl
        self._cache: Dict[str, float] = {}
        self._lock    = threading.Lock()

    def mark_unhealthy(self, provider: str):
        with self._lock:
            self._cache[provider] = time.time()

    def is_healthy(self, provider: str) -> bool:
        with self._lock:
            if provider not in self._cache:
                return True
            if time.time() - self._cache[provider] > self.ttl:
                del self._cache[provider]
                return True
            return False

# ---------------------------------------------------------------------------
# History Helper
# ---------------------------------------------------------------------------
def _extract_text_from_turn(turn: dict) -> str:
    """Safely extract text from a history turn, handling string or dict parts."""
    text = turn.get("content")
    if not text:
        parts = turn.get("parts", [])
        if parts:
            part = parts[0]
            if isinstance(part, dict):
                text = part.get("text", "")
            else:
                text = str(part)
    return text or ""

# ---------------------------------------------------------------------------
# Provider Manager
# ---------------------------------------------------------------------------
class ProviderManager:
    """
    Orchestrates provider selection, failover, retries, circuit breaking,
    metrics, and health caching.
    """
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.metrics      = ProviderMetrics()
        self.health_cache = HealthCheckCache()
        self._lock        = threading.Lock()

    # -- internal helpers ---------------------------------------------------
    def _get_breaker(self, provider: str) -> CircuitBreaker:
        with self._lock:
            if provider not in self.circuit_breakers:
                self.circuit_breakers[provider] = CircuitBreaker()
            return self.circuit_breakers[provider]

    def _get_setting(self, key: str) -> Optional[str]:
        """Read a single Setting row. Returns None when missing."""
        try:
            row = Setting.query.filter_by(key=key).first()
            return row.value if row and row.value else None
        except Exception:
            return None

    # -- provider resolution ------------------------------------------------
    def resolve_active_provider(self) -> str:
        explicit = self._get_setting("ai_provider")
        if explicit:
            candidate = explicit.strip().lower()
            if candidate in KNOWN_PROVIDERS:
                return candidate
            _get_logger().warning(
                f"ai_provider Setting contains unknown value '{explicit}'. "
                f"Falling back to auto-detection."
            )

        legacy_key = (
            self._get_setting("gemini_api_key")
            or current_app.config.get("GEMINI_API_KEY", "")
        )
        if legacy_key:
            return self.detect_provider_from_key(legacy_key.strip())

        return "gemini"

    @staticmethod
    def detect_provider_from_key(api_key: str) -> str:
        if api_key.startswith("gsk_"): return "groq"
        if api_key.startswith("sk-ant"): return "claude"
        if api_key.startswith("sk-or-"): return "openrouter"
        if api_key.startswith("sk-"): return "openai"
        return "gemini"

    def detect_provider(self, api_key: str) -> str:
        return self.detect_provider_from_key(api_key)

    def get_active_provider(self) -> str:
        return self.resolve_active_provider()

    def get_available_providers(self) -> List[str]:
        priority = self._get_provider_priority()
        active   = self.resolve_active_provider()
        ordered: List[str] = [active]
        for p in priority:
            if p not in ordered:
                ordered.append(p)
        return ordered

    def _get_provider_priority(self) -> List[str]:
        # Fallback is opt-in. An absent setting means one provider call only,
        # preventing surprise token/cost multiplication.
        raw = self._get_setting("provider_fallbacks") or self._get_setting("provider_priority")
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list) and parsed:
                    valid = [p.lower().strip() for p in parsed if p.lower().strip() in KNOWN_PROVIDERS]
                    if valid:
                        return valid
            except (json.JSONDecodeError, TypeError):
                pass
        return list(DEFAULT_PRIORITY)

    # -- API key resolution -------------------------------------------------
    def get_api_key_for_provider(self, provider: str) -> str:
        provider = provider.lower().strip()
        setting_key = API_KEY_SETTING_KEYS.get(provider)
        if setting_key:
            value = self._get_setting(setting_key)
            if value:
                return value.strip()

        if provider == "gemini":
            value = self._get_setting("gemini_api_key")
            if value:
                return value.strip()
            value = current_app.config.get("GEMINI_API_KEY", "")
            if value:
                return value.strip()

        raise RuntimeError(
            f"No API key configured for provider '{provider}'. "
            f"Please set '{setting_key or provider + '_api_key'}' in the Admin Panel."
        )

    def get_api_key(self, provider: str = None) -> str:
        if provider is None:
            provider = self.get_active_provider()
        return self.get_api_key_for_provider(provider)

    # -- model resolution ---------------------------------------------------
    def get_model_for_provider(self, provider: str) -> str:
        setting_key = MODEL_SETTING_KEYS.get(provider)
        if setting_key:
            value = self._get_setting(setting_key)
            if value:
                return value.strip()
        if provider == "gemini":
            configured = current_app.config.get("GEMINI_MODEL", "")
            if configured:
                return configured.strip()
        return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["gemini"])

    # -- base-URL resolution ------------------------------------------------
    def get_base_url_for_provider(self, provider: str) -> str:
        setting_key = BASE_URL_SETTING_KEYS.get(provider)
        if setting_key:
            value = self._get_setting(setting_key)
            if value:
                return value.strip()
        return DEFAULT_BASE_URLS.get(provider, "")

    # -- system instruction -------------------------------------------------
    def _get_system_instruction(self, system_context: str) -> str:
        db_row = None
        try:
            db_row = Setting.query.filter_by(key="system_prompt").first()
        except Exception:
            pass

        base = (
            db_row.value
            if db_row and db_row.value
            else (
                "You are Isolde, a helpful, honest AI assistant. "
                "If context is provided below, ground your answer in it."
            )
        )
        if system_context:
            return f"{base}\n\n{system_context}"
        return base

    # -- retry with backoff -------------------------------------------------
    def _execute_with_retry(self, func, provider: str, timeout: Optional[int] = None) -> ProviderResponse:
        timeout = timeout or DEFAULT_TIMEOUT
        breaker = self._get_breaker(provider)
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            if not breaker.allow_request():
                last_error = f"Circuit breaker open for {provider}"
                break
            if not self.health_cache.is_healthy(provider):
                last_error = f"Health cache: {provider} unhealthy"
                break

            start = time.time()
            try:
                result = func(timeout)
                usage = {}
                if isinstance(result, tuple):
                    result, usage = result
                latency = (time.time() - start) * 1000
                self.metrics.record(provider, latency, True)
                breaker.record_success()
                return ProviderResponse(
                    success=True,
                    text=result,
                    provider=provider,
                    model=self.get_model_for_provider(provider),
                    latency_ms=latency,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    tokens_used=usage.get("total_tokens"),
                )
            except RuntimeError as conf_err:
                # Configuration errors (missing key, invalid URL) should not be retried
                latency = (time.time() - start) * 1000
                self.metrics.record(provider, latency, False)
                last_error = str(conf_err)
                _get_logger().error(f"Provider '{provider}' configuration error: {conf_err}")
                return ProviderResponse(success=False, error=last_error, provider=provider)
            except Exception as exc:
                latency = (time.time() - start) * 1000
                self.metrics.record(provider, latency, False)
                breaker.record_failure()
                last_error = str(exc)
                _get_logger().warning(
                    f"Provider '{provider}' attempt {attempt}/{MAX_RETRIES} failed: {exc}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))

        # If we exhausted retries or breaker/health cache blocked us
        if "Circuit breaker" not in last_error and "Health cache" not in last_error:
            self.health_cache.mark_unhealthy(provider)

        return ProviderResponse(success=False, error=last_error, provider=provider)

    # -----------------------------------------------------------------------
    # Provider call implementations
    # -----------------------------------------------------------------------
    def _call_gemini(self, prompt: str, history, sys_prompt: str, timeout: int):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RuntimeError("google-genai package is not installed. Run: pip install google-genai")

        api_key    = self.get_api_key_for_provider("gemini")
        model_name = self.get_model_for_provider("gemini")
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta", timeout=int(timeout * 1000)),
        )
        chat = client.chats.create(
            model=model_name,
            history=_to_content_history(history),
            config=types.GenerateContentConfig(system_instruction=sys_prompt),
        )
        response = chat.send_message(message=prompt)
        usage = response.usage_metadata
        return (response.text or "").strip(), {
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
        }

    def _call_gemini_stream(self, prompt: str, history, sys_prompt: str, timeout: int) -> Generator[str, None, None]:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RuntimeError("google-genai package is not installed.")

        api_key    = self.get_api_key_for_provider("gemini")
        model_name = self.get_model_for_provider("gemini")
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta", timeout=int(timeout * 1000)),
        )
        chat = client.chats.create(
            model=model_name,
            history=_to_content_history(history),
            config=types.GenerateContentConfig(system_instruction=sys_prompt),
        )
        for chunk in chat.send_message_stream(message=prompt):
            text = chunk.text or ""
            if text:
                yield text

    # -- OpenAI-compatible generic call ------------------------------------
    def _call_openai_compatible(
        self,
        provider: str,
        prompt: str,
        history,
        sys_prompt: str,
        timeout: int,
        stream: bool = False,
    ):
        api_key  = self.get_api_key_for_provider(provider)
        model    = self.get_model_for_provider(provider)
        base_url = self.get_base_url_for_provider(provider)
        if not base_url:
            raise RuntimeError(f"Base URL for {provider} is not configured.")

        messages = [{"role": "system", "content": sys_prompt}]
        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role not in ("user", "assistant", "system"):
                    role = "user"
                text = _extract_text_from_turn(turn)
                if text:
                    messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://isolde.ai"
            headers["X-Title"] = "Isolde AI"

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        session = _get_http_session()
        resp = session.post(base_url, headers=headers, json=payload, timeout=timeout, stream=stream)

        if resp.status_code != 200:
            raise RuntimeError(f"{provider} API Error ({resp.status_code}): {resp.text[:500]}")

        if not stream:
            try:
                data = resp.json()
                if "error" in data:
                    raise RuntimeError(f"{provider} API Error: {data['error'].get('message', str(data['error']))}")
                usage = data.get("usage") or {}
                return data["choices"][0]["message"]["content"].strip(), {
                    "input_tokens": usage.get("prompt_tokens"),
                    "output_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            except (KeyError, IndexError, TypeError, ValueError):
                raise RuntimeError(f"{provider} API returned malformed response: {resp.text[:200]}")

        def gen():
            try:
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            obj = json.loads(data_str)
                            if "error" in obj:
                                err_msg = obj["error"].get("message", str(obj["error"]))
                                raise RuntimeError(f"{provider} Stream Error: {err_msg}")
                            choices = obj.get("choices")
                            if choices:
                                content = (choices[0].get("delta") or {}).get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
            finally:
                resp.close()
        return gen()

    # -- Concrete provider wrappers ----------------------------------------
    def _call_groq(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("groq", prompt, history, sys_prompt, timeout)

    def _call_groq_stream(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("groq", prompt, history, sys_prompt, timeout, stream=True)

    def _call_openai(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("openai", prompt, history, sys_prompt, timeout)

    def _call_openai_stream(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("openai", prompt, history, sys_prompt, timeout, stream=True)

    def _call_openrouter(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("openrouter", prompt, history, sys_prompt, timeout)

    def _call_openrouter_stream(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("openrouter", prompt, history, sys_prompt, timeout, stream=True)

    def _call_deepseek(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("deepseek", prompt, history, sys_prompt, timeout)

    def _call_deepseek_stream(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("deepseek", prompt, history, sys_prompt, timeout, stream=True)

    def _call_mistral(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("mistral", prompt, history, sys_prompt, timeout)

    def _call_mistral_stream(self, prompt, history, sys_prompt, timeout):
        return self._call_openai_compatible("mistral", prompt, history, sys_prompt, timeout, stream=True)

    # -- Claude (non-OpenAI-compatible) ------------------------------------
    def _call_claude(self, prompt, history, sys_prompt, timeout):
        api_key = self.get_api_key_for_provider("claude")
        model   = self.get_model_for_provider("claude")
        messages = []
        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role not in ("user", "assistant"):
                    role = "user"
                text = _extract_text_from_turn(turn)
                if text:
                    messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = {
            "model": model,
            "system": sys_prompt,
            "messages": messages,
            "max_tokens": 4096,
        }

        session = _get_http_session()
        resp = session.post("https://api.anthropic.com/v1/messages", headers=headers, json=data, timeout=timeout)

        if resp.status_code != 200:
            raise RuntimeError(f"Claude Error ({resp.status_code}): {resp.text[:500]}")

        try:
            resp_data = resp.json()
            if "error" in resp_data:
                raise RuntimeError(f"Claude API Error: {resp_data['error'].get('message', str(resp_data['error']))}")
            usage = resp_data.get("usage") or {}
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            total_tokens = (
                input_tokens + output_tokens
                if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                else None
            )
            return resp_data["content"][0]["text"].strip(), {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }
        except (KeyError, IndexError, TypeError, ValueError):
            raise RuntimeError(f"Claude API returned malformed response: {resp.text[:200]}")

    def _call_claude_stream(self, prompt, history, sys_prompt, timeout):
        api_key = self.get_api_key_for_provider("claude")
        model   = self.get_model_for_provider("claude")
        messages = []
        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role not in ("user", "assistant"):
                    role = "user"
                text = _extract_text_from_turn(turn)
                if text:
                    messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = {
            "model": model,
            "system": sys_prompt,
            "messages": messages,
            "max_tokens": 4096,
            "stream": True,
        }

        session = _get_http_session()
        resp = session.post("https://api.anthropic.com/v1/messages", headers=headers, json=data, timeout=timeout, stream=True)

        if resp.status_code != 200:
            raise RuntimeError(f"Claude Stream Error ({resp.status_code}): {resp.text[:500]}")

        def gen():
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        obj = json.loads(data_str)
                        if obj.get("type") == "error":
                            err_msg = obj.get("error", {}).get("message", str(obj.get("error")))
                            raise RuntimeError(f"Claude Stream Error: {err_msg}")
                        if obj.get("type") == "content_block_delta":
                            delta = obj.get("delta") or {}
                            text = delta.get("text", "")
                            if text:
                                yield text
                        elif obj.get("type") == "message_stop":
                            break
                    except json.JSONDecodeError:
                        continue
                    except RuntimeError:
                        raise
                    except Exception:
                        continue
        return gen()

    # -- dispatch tables ----------------------------------------------------
    def _get_call_fn(self, provider: str):
        dispatch = {
            "gemini":     self._call_gemini,
            "groq":       self._call_groq,
            "openai":     self._call_openai,
            "claude":     self._call_claude,
            "openrouter": self._call_openrouter,
            "deepseek":   self._call_deepseek,
            "mistral":    self._call_mistral,
        }
        return dispatch.get(provider)

    def _get_stream_fn(self, provider: str):
        dispatch = {
            "gemini":     self._call_gemini_stream,
            "groq":       self._call_groq_stream,
            "openai":     self._call_openai_stream,
            "claude":     self._call_claude_stream,
            "openrouter": self._call_openrouter_stream,
            "deepseek":   self._call_deepseek_stream,
            "mistral":    self._call_mistral_stream,
        }
        return dispatch.get(provider)

    # -----------------------------------------------------------------------
    # Public generation API
    # -----------------------------------------------------------------------
    def generate(self, prompt, history=None, system_context="", timeout=None) -> ProviderResponse:
        sys_prompt = self._get_system_instruction(system_context)
        providers  = self.get_available_providers()

        for provider in providers:
            fn = self._get_call_fn(provider)
            if fn is None:
                continue

            def call_fn(t, _fn=fn, _p=prompt, _h=history, _s=sys_prompt):
                return _fn(_p, _h, _s, t)

            result = self._execute_with_retry(call_fn, provider, timeout)
            if result.success:
                return result

            _get_logger().warning(
                f"Provider '{provider}' failed: {result.error}. Trying next."
            )

        return ProviderResponse(success=False, error="All providers failed or unavailable.")

    def generate_stream(
        self, prompt, history=None, system_context="", timeout=None, cancel_event=None
    ) -> Generator[str, None, None]:
        sys_prompt = self._get_system_instruction(system_context)
        providers  = self.get_available_providers()

        for provider in providers:
            fn = self._get_stream_fn(provider)
            if fn is None:
                continue

            breaker = self._get_breaker(provider)
            if not breaker.allow_request():
                continue
            if not self.health_cache.is_healthy(provider):
                continue

            start = time.time()
            try:
                stream = fn(prompt, history, sys_prompt, timeout or DEFAULT_TIMEOUT)
                for chunk in stream:
                    if cancel_event is not None and cancel_event.is_set():
                        close = getattr(stream, "close", None)
                        if callable(close):
                            close()
                        return
                    yield chunk
                latency = (time.time() - start) * 1000
                self.metrics.record(provider, latency, True)
                breaker.record_success()
                return
            except RuntimeError as conf_err:
                _get_logger().error(f"Provider '{provider}' streaming configuration error: {conf_err}")
                self.metrics.record(provider, (time.time() - start) * 1000, False)
                continue
            except Exception as exc:
                latency = (time.time() - start) * 1000
                self.metrics.record(provider, latency, False)
                breaker.record_failure()
                self.health_cache.mark_unhealthy(provider)
                _get_logger().exception(f"Provider '{provider}' streaming failed with {type(exc).__name__}")
                continue

        yield "[ERROR] All providers failed."

    def get_metrics(self) -> Dict:
        return self.metrics.get_all()

    def get_provider_health(self) -> Dict[str, bool]:
        return {p: self.health_cache.is_healthy(p) for p in KNOWN_PROVIDERS}

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_manager: Optional[ProviderManager] = None
_manager_lock = threading.Lock()

def get_provider_manager() -> ProviderManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ProviderManager()
    return _manager

# ---------------------------------------------------------------------------
# History conversion helper (preserved from original)
# ---------------------------------------------------------------------------
def _to_content_history(history):
    if not history:
        return []
    try:
        from google.genai import types
    except ImportError:
        return []

    contents = []
    for turn in history:
        role = turn.get("role", "user")
        if role == "assistant":
            role = "model"
        elif role not in ("user", "model"):
            role = "user"

        text = _extract_text_from_turn(turn)
        if not text:
            continue

        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents

# ---------------------------------------------------------------------------
# Workspace & Agent Context Builder (preserved from original)
# ---------------------------------------------------------------------------
def _build_agent_workspace_context(
    agent_id=None,
    workspace_id=None,
    project_id=None,
) -> str:
    try:
        from app.models.workspace_model import Agent, Workspace, Project, WorkspaceDocument
    except ImportError:
        return ""

    context_blocks: List[str] = []

    if agent_id:
        try:
            agent = Agent.query.get(agent_id)
            if agent and agent.is_active:
                agent_block = f"ACTIVE AGENT PERSONA ({agent.name}):\n{agent.system_prompt}"
                if agent.role_description:
                    agent_block += f"\nRole: {agent.role_description}"
                context_blocks.append(agent_block)
        except Exception:
            pass

    if workspace_id:
        try:
            workspace = Workspace.query.get(workspace_id)
            if workspace:
                docs = WorkspaceDocument.query.filter_by(
                    workspace_id=workspace_id, project_id=None
                ).limit(5).all()
                doc_snippets = [d.extracted_text[:1500] for d in docs if d.extracted_text]
                if doc_snippets:
                    context_blocks.append(
                        f"WORKSPACE KNOWLEDGE ({workspace.name}):\n"
                        + "\n---\n".join(doc_snippets)
                    )
        except Exception:
            pass

    if project_id:
        try:
            project = Project.query.get(project_id)
            if project:
                proj_docs = WorkspaceDocument.query.filter_by(project_id=project_id).limit(5).all()
                proj_snippets = [d.extracted_text[:1500] for d in proj_docs if d.extracted_text]
                proj_block = f"ACTIVE PROJECT ({project.name})"
                if project.description:
                    proj_block += f": {project.description}"
                if proj_snippets:
                    proj_block += "\nProject documents:\n" + "\n---\n".join(proj_snippets)
                context_blocks.append(proj_block)
        except Exception:
            pass

    return "\n\n".join(context_blocks)

# ---------------------------------------------------------------------------
# Backward-compatible public API
# ---------------------------------------------------------------------------
def generate_reply(
    prompt: str,
    history=None,
    system_context: str = "",
    agent_id=None,
    workspace_id=None,
    project_id=None,
) -> str:
    phase4_context  = _build_agent_workspace_context(agent_id, workspace_id, project_id)
    combined_context = system_context or ""
    if phase4_context:
        combined_context = f"{combined_context}\n\n{phase4_context}".strip()

    manager = get_provider_manager()
    result  = manager.generate(prompt, history=history, system_context=combined_context)
    if result.success:
        return result.text
    raise RuntimeError(result.error or "AI service unavailable.")


def generate_reply_with_usage(
    prompt: str,
    history=None,
    system_context: str = "",
) -> ProviderResponse:
    """Generate a reply while preserving authoritative provider usage metadata."""
    result = get_provider_manager().generate(
        prompt, history=history, system_context=system_context
    )
    if not result.success:
        raise RuntimeError(result.error or "AI service unavailable.")
    return result

def generate_reply_stream(
    prompt: str,
    history=None,
    system_context: str = "",
    agent_id=None,
    workspace_id=None,
    project_id=None,
    cancel_event=None,
) -> Generator[str, None, None]:
    phase4_context  = _build_agent_workspace_context(agent_id, workspace_id, project_id)
    combined_context = system_context or ""
    if phase4_context:
        combined_context = f"{combined_context}\n\n{phase4_context}".strip()

    manager = get_provider_manager()
    yield from manager.generate_stream(
        prompt, history=history, system_context=combined_context,
        cancel_event=cancel_event,
    )

def embed_text(text: str):
    manager  = get_provider_manager()
    provider = manager.resolve_active_provider()

    if provider == "openai":
        api_key = manager.get_api_key_for_provider("openai")
        session = _get_http_session()
        resp = session.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "text-embedding-3-small", "input": text},
            timeout=30,
        )
        if resp.status_code == 200:
            try:
                return resp.json()["data"][0]["embedding"]
            except (KeyError, IndexError, TypeError, ValueError):
                raise RuntimeError("OpenAI Embedding returned malformed response.")
        raise RuntimeError(f"OpenAI Embedding Error ({resp.status_code}): {resp.text[:300]}")

    if provider in ("groq", "claude", "mistral", "deepseek", "openrouter"):
        raise RuntimeError(
            f"Embeddings are not natively supported by provider '{provider}'. "
            "Please configure a Gemini or OpenAI API key for RAG embeddings."
        )

    try:
        from google import genai
    except ImportError:
        raise RuntimeError("google-genai package is not installed.")

    api_key = manager.get_api_key_for_provider("gemini")
    client  = genai.Client(api_key=api_key)
    result  = client.models.embed_content(model="gemini-embedding-2", contents=text)
    return list(result.embeddings[0].values)

def analyze_image(image_bytes: bytes, mime_type: str, question: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai package is not installed.")

    manager    = get_provider_manager()
    api_key    = manager.get_api_key_for_provider("gemini")
    model_name = manager.get_model_for_provider("gemini")
    client   = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            question,
        ],
    )
    return (response.text or "").strip()
