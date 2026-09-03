"""Opt-in smoke test for a deployed ISOLDE instance using real integrations."""
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_EXTERNAL_E2E") != "1",
    reason="real external E2E credentials were not supplied",
)


def _required_environment(name):
    value = os.getenv(name, "").strip()
    if not value:
        pytest.fail(f"Missing required external E2E environment variable: {name}")
    return value


def _expect_status(response, expected, operation):
    assert response.status_code == expected, (
        f"{operation} returned HTTP {response.status_code}; "
        f"request_id={response.headers.get('X-Request-ID', 'unavailable')}"
    )


def test_real_production_auth_provider_stream_research_rag_and_logout():
    base_url = _required_environment("ISOLDE_E2E_BASE_URL").rstrip("/")
    parsed = urlsplit(base_url)
    assert (
        parsed.scheme == "https"
        and parsed.netloc
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    ), "ISOLDE_E2E_BASE_URL must be an HTTPS origin"
    email = _required_environment("ISOLDE_E2E_EMAIL")
    password = _required_environment("ISOLDE_E2E_PASSWORD")
    timeout = float(os.getenv("ISOLDE_E2E_TIMEOUT_SECONDS", "30"))
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    _expect_status(session.get(f"{base_url}/api/live", timeout=timeout), 200, "liveness")
    _expect_status(session.get(f"{base_url}/api/ready", timeout=timeout), 200, "readiness")
    capabilities_response = session.get(f"{base_url}/api/capabilities", timeout=timeout)
    _expect_status(capabilities_response, 200, "capabilities")
    versioned_response = session.get(f"{base_url}/api/v1/capabilities", timeout=timeout)
    _expect_status(versioned_response, 200, "versioned capabilities")
    capabilities = capabilities_response.json()["capabilities"]
    assert capabilities == versioned_response.json()["capabilities"]
    assert capabilities["ai"] == "AVAILABLE"
    assert capabilities["ai_streaming"] == "AVAILABLE"
    assert capabilities["api_access"] == "AVAILABLE"

    login = session.post(
        f"{base_url}/api/login", json={"email": email, "password": password}, timeout=timeout,
    )
    _expect_status(login, 200, "login")
    token = login.json().get("access_token")
    assert token, "login returned no access token"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        chat = session.post(
            f"{base_url}/api/v1/chat", headers=headers,
            json={"message": os.getenv("ISOLDE_E2E_CHAT_PROMPT", "Reply briefly with READY.")},
            timeout=timeout,
        )
        _expect_status(chat, 200, "provider chat")
        assert chat.json().get("reply"), "provider chat returned no answer"

        stream = session.post(
            f"{base_url}/api/chat/stream", headers=headers,
            json={"message": os.getenv("ISOLDE_E2E_STREAM_PROMPT", "Reply briefly with STREAM READY."), "research_mode": "off"},
            timeout=timeout,
        )
        _expect_status(stream, 200, "provider stream")
        stream_text = stream.text
        assert '"delta"' in stream_text and "[DONE]" in stream_text and "[ERROR]" not in stream_text

        if capabilities.get("rag") == "AVAILABLE":
            rag = session.post(
                f"{base_url}/api/v1/rag/query", headers=headers,
                json={"query": os.getenv("ISOLDE_E2E_RAG_QUERY", "production readiness"), "top_k": 3},
                timeout=timeout,
            )
            _expect_status(rag, 200, "RAG query")
            assert isinstance(rag.json().get("data", {}).get("chunks"), list)

        if capabilities.get("research") == "AVAILABLE":
            research = session.post(
                f"{base_url}/api/v1/research", headers=headers,
                json={"question": os.getenv("ISOLDE_E2E_RESEARCH_QUERY", "What is the latest stable Python release?")},
                timeout=timeout,
            )
            _expect_status(research, 200, "research")
            data = research.json().get("data", {})
            assert data.get("sources") and data.get("citations"), "research returned no validated citations"

        upload_path = os.getenv("ISOLDE_E2E_UPLOAD_FILE", "").strip()
        if upload_path:
            assert capabilities.get("rag") == "AVAILABLE", (
                "ISOLDE_E2E_UPLOAD_FILE requires the deployed RAG capability to be AVAILABLE"
            )
            path = Path(upload_path)
            assert path.is_file(), "ISOLDE_E2E_UPLOAD_FILE does not identify a file"
            with path.open("rb") as handle:
                upload = session.post(
                    f"{base_url}/api/rag/upload", headers=headers,
                    files={"file": (path.name, handle)}, timeout=timeout,
                )
            _expect_status(upload, 200, "RAG upload")
            assert upload.json().get("chunks_indexed", 0) > 0
    finally:
        logout = session.post(f"{base_url}/api/logout", headers=headers, timeout=timeout)
        _expect_status(logout, 200, "logout")
