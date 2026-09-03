def test_public_capabilities_are_truthful_and_secret_free(client, app):
    app.config.update({
        "GEMINI_API_KEY": "",
        "TAVILY_API_KEY": "",
        "GOOGLE_OAUTH_CLIENT_ID": "",
        "GOOGLE_OAUTH_CLIENT_SECRET": "",
        "GOOGLE_OAUTH_REDIRECT_URI": "",
        "CANCELLATION_REDIS_URL": "",
    })
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    assert response.get_json() == {"capabilities": {
        "ai": "NOT_CONFIGURED", "ai_streaming": "NOT_CONFIGURED", "rag": "NOT_CONFIGURED",
        "research": "NOT_CONFIGURED", "google_oauth": "NOT_CONFIGURED",
        "oauth": "NOT_CONFIGURED", "api_access": "AVAILABLE",
        "cancellation": "NOT_CONFIGURED", "admin": "AVAILABLE",
        "deep_research": "NOT_SUPPORTED", "pgvector": "NOT_SUPPORTED",
        "tavily_research": "NOT_CONFIGURED", "file_upload": "AVAILABLE",
        "image_generation": "NOT_CONFIGURED", "video_generation": "NOT_CONFIGURED",
    }}


def test_public_capabilities_report_configured_integrations_without_secrets(client, app):
    app.config.update({
        "GEMINI_API_KEY": "provider-secret", "TAVILY_API_KEY": "research-secret",
        "GOOGLE_OAUTH_CLIENT_ID": "client-id", "GOOGLE_OAUTH_CLIENT_SECRET": "client-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "https://example.test/callback",
        "CANCELLATION_REDIS_URL": "redis://secret@localhost:6379/0",
    })
    response = client.get("/api/capabilities")
    payload = response.get_json()
    assert payload["capabilities"]["ai"] == "AVAILABLE"
    assert payload["capabilities"]["ai_streaming"] == "AVAILABLE"
    assert payload["capabilities"]["research"] == "AVAILABLE"
    assert payload["capabilities"]["tavily_research"] == "AVAILABLE"
    assert payload["capabilities"]["google_oauth"] == "AVAILABLE"
    assert payload["capabilities"]["oauth"] == "AVAILABLE"
    assert payload["capabilities"]["api_access"] == "AVAILABLE"
    assert payload["capabilities"]["cancellation"] == "AVAILABLE"
    assert payload["capabilities"]["pgvector"] == "NOT_SUPPORTED"
    assert "secret" not in response.get_data(as_text=True)


def test_public_capabilities_do_not_claim_configured_unsupported_media_is_available(client, app):
    app.config.update({"IMAGE_PROVIDER": "future-provider", "VIDEO_PROVIDER": "future-provider"})
    capabilities = client.get("/api/capabilities").get_json()["capabilities"]
    assert capabilities["image_generation"] == "NOT_SUPPORTED"
    assert capabilities["video_generation"] == "NOT_SUPPORTED"
