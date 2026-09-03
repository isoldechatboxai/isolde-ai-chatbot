from app.services import research_service
from app.routes.chat_routes import _research_sse_events
import json
import socket
import pytest


def test_intent_planning_avoids_web_for_stable_questions():
    plan = research_service.classify_intent("Explain Python decorators")
    assert plan.intent == "EXPLANATION"
    assert plan.requires_web is False


def test_intent_planning_requires_web_for_current_questions():
    plan = research_service.classify_intent("What are the latest API changes?")
    assert plan.intent == "CURRENT_INFORMATION"
    assert plan.requires_web is True
    assert plan.max_sources <= 5


def test_canonical_url_rejects_ssrf_targets():
    assert research_service._canonical_url("http://127.0.0.1/admin") is None
    assert research_service._canonical_url("http://10.0.0.2/metadata") is None
    assert research_service._canonical_url("https://docs.example.test/path#fragment") == "https://docs.example.test/path"


def test_research_capability_is_truthful_when_unconfigured(app):
    app.config["TAVILY_API_KEY"] = ""
    with app.app_context():
        assert research_service.capability()["status"] == "NOT_CONFIGURED"
        try:
            research_service.research("latest release notes", requested=True)
        except research_service.ResearchUnavailable as error:
            assert str(error) == "RESEARCH_PROVIDER_NOT_CONFIGURED"
        else:
            raise AssertionError("research should not silently fall back without a configured provider")


def test_research_capability_does_not_claim_health_from_a_secret(app):
    app.config["TAVILY_API_KEY"] = "configured-only"
    with app.app_context():
        assert research_service.capability()["status"] == "CONFIGURED"


def test_snippet_only_result_validates_citations_and_independence(app):
    sources = [
        {"id": "web-1", "url": "https://one.example.test/a", "title": "One", "domain": "one.example.test", "snippet": "Evidence one"},
        {"id": "web-2", "url": "https://two.example.test/b", "title": "Two", "domain": "two.example.test", "snippet": "Evidence two"},
    ]
    with app.app_context():
        result = research_service.build_result("Research a topic", True, sources)
    assert result["plan"]["evidence_mode"] == "SNIPPET_ONLY"
    assert len(result["citations"]) == 2
    assert result["cross_check"]["status"] == "INSUFFICIENT_EVIDENCE"


def test_fetcher_rejects_http_and_private_dns(monkeypatch):
    source = {"id": "web-1", "url": "http://public.example.test/", "canonical_url": "http://public.example.test/"}
    with pytest.raises(research_service.ResearchFetchBlocked):
        research_service.fetch_evidence(source)

    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.1", 443))])
    source["url"] = source["canonical_url"] = "https://public.example.test/"
    with pytest.raises(research_service.ResearchFetchBlocked):
        research_service.fetch_evidence(source)


def test_html_extraction_strips_active_content(monkeypatch):
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/html"}
        encoding = "utf-8"
        def raise_for_status(self): pass
        def iter_content(self, _size): yield b"<title>Title</title><script>steal()</script><style>x</style><h1>Heading</h1><p>Safe text</p>"
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))])
    monkeypatch.setattr(research_service.requests, "get", lambda *args, **kwargs: Response())
    evidence = research_service.fetch_evidence({"id": "web-1", "url": "https://public.example.test/"})
    assert evidence["evidence_mode"] == "FULL_PAGE"
    assert "Safe text" in evidence["text"]
    assert "steal" not in evidence["text"]


def test_fetcher_stops_reading_after_byte_budget(monkeypatch):
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/plain"}
        encoding = "utf-8"
        def raise_for_status(self): pass
        def iter_content(self, _size):
            yield b"abc"
            yield b"def"
            raise AssertionError("fetcher read past its byte budget")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))])
    monkeypatch.setattr(research_service.requests, "get", lambda *args, **kwargs: Response())
    evidence = research_service.fetch_evidence({"id": "web-1", "url": "https://public.example.test/"}, max_bytes=4)
    assert evidence["text"] == "abcd"
    assert evidence["truncated"] is True


def test_cross_check_requires_independent_identical_evidence():
    sources = [
        {"id": "web-1", "domain": "one.example.test"},
        {"id": "web-2", "domain": "two.example.test"},
    ]
    evidence = [
        {"source_id": "web-1", "claim": "Release date", "evidence": "Release date is October 1."},
        {"source_id": "web-2", "claim": "Release date", "evidence": "Release date is October 1."},
    ]
    result = research_service.cross_check_evidence(evidence, sources)
    assert result["status"] == "AGREEMENT"
    assert result["agreements"][0]["source_ids"] == ["web-1", "web-2"]


def test_research_sse_events_are_typed_and_never_deltas():
    result = {
        "intent": "RESEARCH", "plan": {"evidence_mode": "SNIPPET_ONLY"},
        "sources": [{"id": "web-1"}],
        "evidence": [{"source_id": "web-1"}],
        "cross_check": {"status": "INSUFFICIENT_EVIDENCE"},
        "citations": [{"source_id": "web-1"}],
    }
    payloads = [json.loads(item.removeprefix("data: ").strip()) for item in _research_sse_events(result)]
    assert [payload["event"] for payload in payloads] == [
        "research_started", "research_source", "research_evidence",
        "research_cross_check", "research_citation",
    ]
    assert all("delta" not in payload for payload in payloads)
