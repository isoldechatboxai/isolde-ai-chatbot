import threading

from app.services.provider_router import ProviderManager


def test_fallback_is_opt_in(app, monkeypatch):
    manager = ProviderManager()
    monkeypatch.setattr(manager, "resolve_active_provider", lambda: "gemini")
    monkeypatch.setattr(manager, "_get_setting", lambda key: None)
    assert manager.get_available_providers() == ["gemini"]


def test_explicit_fallback_is_bounded_and_deduplicated(app, monkeypatch):
    manager = ProviderManager()
    monkeypatch.setattr(manager, "resolve_active_provider", lambda: "gemini")
    monkeypatch.setattr(
        manager, "_get_setting",
        lambda key: '["openai", "gemini", "unknown", "openai"]' if key == "provider_fallbacks" else None,
    )
    assert manager.get_available_providers() == ["gemini", "openai"]


def test_provider_response_preserves_authoritative_usage(app, monkeypatch):
    manager = ProviderManager()
    monkeypatch.setattr(manager, "get_model_for_provider", lambda provider: "test-model")
    result = manager._execute_with_retry(
        lambda timeout: ("answer", {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}),
        "gemini",
    )
    assert result.success is True
    assert result.input_tokens == 7
    assert result.output_tokens == 3
    assert result.tokens_used == 10


def test_gemini_uses_configured_model_timeout_and_usage(app, monkeypatch):
    from google import genai

    captured = {}

    class Usage:
        prompt_token_count = 11
        candidates_token_count = 4
        total_token_count = 15

    class Response:
        text = "verified response"
        usage_metadata = Usage()

    class Chat:
        def send_message(self, message):
            captured["message"] = message
            return Response()

    class Chats:
        def create(self, **kwargs):
            captured.update(kwargs)
            return Chat()

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chats = Chats()

    monkeypatch.setattr(genai, "Client", Client)
    manager = ProviderManager()
    monkeypatch.setattr(manager, "get_api_key_for_provider", lambda provider: "secret-not-logged")
    app.config["GEMINI_MODEL"] = "gemini-3.7-flash"
    text, usage = manager._call_gemini("hello", [], "system", 9)
    assert text == "verified response"
    assert captured["model"] == "gemini-3.7-flash"
    assert captured["client"]["http_options"].timeout == 9000
    assert usage == {"input_tokens": 11, "output_tokens": 4, "total_tokens": 15}


def test_stream_cancellation_closes_provider_generator(app, monkeypatch):
    manager = ProviderManager()
    closed = {"value": False}

    def provider_stream(*args):
        try:
            yield "first"
            yield "second"
        finally:
            closed["value"] = True

    monkeypatch.setattr(manager, "get_available_providers", lambda: ["gemini"])
    monkeypatch.setattr(manager, "_get_stream_fn", lambda provider: provider_stream)
    event = threading.Event()
    event.set()
    assert list(manager.generate_stream("hello", cancel_event=event)) == []
    assert closed["value"] is True
