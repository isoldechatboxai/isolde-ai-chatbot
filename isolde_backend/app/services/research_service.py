"""Bounded, provider-optional web research primitives for chat routes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
import socket
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

import requests
from flask import current_app, has_app_context


class ResearchUnavailable(RuntimeError):
    """Raised when requested web research has no usable configured provider."""


class ResearchProviderError(RuntimeError):
    """Raised when a configured research provider cannot complete safely."""


class ResearchFetchBlocked(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.blocked=0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "template"}: self.blocked += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "template"} and self.blocked: self.blocked -= 1
    def handle_data(self, data):
        if not self.blocked: self.parts.append(data)


def _safe_host(host: str) -> None:
    if not host or host.lower().endswith('.local') or host.lower() == 'localhost':
        raise ResearchFetchBlocked('RESEARCH_FETCH_BLOCKED')
    try: addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc: raise ResearchFetchBlocked('RESEARCH_FETCH_FAILED') from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if not _is_public_address(address):
            raise ResearchFetchBlocked('RESEARCH_FETCH_BLOCKED')


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not any((
        address.is_private, address.is_loopback, address.is_link_local,
        address.is_multicast, address.is_reserved, address.is_unspecified,
    ))


def fetch_evidence(
    source: dict, max_bytes: int = 200_000, max_chars: int = 12_000,
    timeout: int | None = None,
) -> dict:
    """HTTPS-only bounded fetch; validates DNS before every request."""
    if max_bytes <= 0 or max_chars <= 0:
        raise ValueError("fetch limits must be positive")
    url = _canonical_url(str(source.get('canonical_url') or source.get('url') or ''))
    if not url or urlsplit(url).scheme != 'https': raise ResearchFetchBlocked('RESEARCH_FETCH_BLOCKED')
    _safe_host(urlsplit(url).hostname or '')
    timeout = timeout or (current_app.config.get('RESEARCH_HTTP_TIMEOUT_SECONDS', 8) if has_app_context() else 8)
    response = requests.get(url, timeout=(min(3, timeout), timeout), allow_redirects=False, stream=True,
                            headers={'User-Agent': 'IsoldeResearch/1.0'})
    try:
        if 300 <= response.status_code < 400: raise ResearchFetchBlocked('RESEARCH_FETCH_BLOCKED')
        response.raise_for_status(); content_type = response.headers.get('Content-Type','').split(';')[0].lower()
        if content_type not in {'text/html','text/plain','application/json'}: raise ResearchFetchBlocked('RESEARCH_FETCH_BLOCKED')
        # Do not join an unbounded iterator before slicing it: that defeats the
        # response-size limit and permits a remote server to exhaust worker memory.
        chunks, received, oversized = [], 0, False
        for chunk in response.iter_content(8192):
            if not chunk:
                continue
            remaining = max_bytes - received
            if remaining <= 0:
                oversized = True
                break
            if len(chunk) > remaining:
                chunks.append(chunk[:remaining])
                oversized = True
                break
            chunks.append(chunk)
            received += len(chunk)
        body = b''.join(chunks)
        text = body.decode(response.encoding or 'utf-8', errors='replace')
        if content_type == 'text/html':
            parser = _TextExtractor(); parser.feed(text); text = ' '.join(' '.join(parser.parts).split())
        elif content_type == 'application/json':
            try:
                text = json.dumps(json.loads(text), ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                raise ResearchFetchBlocked('RESEARCH_FETCH_INVALID_CONTENT') from exc
        truncated = oversized or len(text) > max_chars; text = text[:max_chars]
        return {'source_id': source['id'], 'canonical_url': url, 'evidence_mode': 'FULL_PAGE',
                'content_type': content_type, 'text': text, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'truncated': truncated}
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


@dataclass(frozen=True)
class ResearchPlan:
    intent: str
    requires_web: bool
    max_sources: int
    max_parallel_requests: int


def build_result(question: str, requested: bool, sources: list[dict]) -> dict:
    """Create a result that distinguishes fetched evidence from search snippets."""
    plan = classify_intent(question)
    evidence = []
    for item in sources:
        fetched = item.get("fetched_evidence") or {}
        evidence_text = fetched.get("text") or item.get("snippet", "")
        if evidence_text:
            evidence.append({"source_id": item["id"], "claim": item["title"],
                             "evidence": evidence_text,
                             "evidence_mode": fetched.get("evidence_mode", "SNIPPET_ONLY"),
                             "confidence": 0.7 if fetched else 0.5})
    cross_check = cross_check_evidence(evidence, sources)
    citations = validate_citations(sources, evidence)
    fetched_count = sum(1 for item in sources if item.get("fetched_evidence"))
    public_sources = [{
        key: item[key] for key in (
            "id", "url", "canonical_url", "title", "snippet", "domain",
            "provider", "retrieved_at", "fetch_status",
        ) if key in item
    } for item in sources]
    return {"question": question, "intent": plan.intent, "research_required": requested,
            "plan": {"source_budget": plan.max_sources,
                     "fetch_budget": min(plan.max_parallel_requests, current_app.config.get("RESEARCH_FETCH_MAX_SOURCES", 2)),
                     "time_budget": current_app.config.get("RESEARCH_HTTP_TIMEOUT_SECONDS", 8),
                     "evidence_mode": "FULL_PAGE" if fetched_count else "SNIPPET_ONLY"}, "sources": public_sources, "evidence": evidence,
            "cross_check": cross_check, "citations": citations,
            "status": "COMPLETED" if sources else "PARTIAL"}


def cross_check_evidence(evidence: list[dict], sources: list[dict]) -> dict:
    """Only report agreement when the same claim is supported by two domains.

    Search snippets are weak evidence.  This deliberately declines to infer
    agreement from merely related snippets, and flags simple explicit negation
    conflicts for the client to surface as unresolved.
    """
    source_domains = {item.get("id"): item.get("domain") for item in sources}
    groups: dict[str, list[dict]] = {}
    for item in evidence:
        claim = " ".join(str(item.get("claim") or "").lower().split())
        domain = source_domains.get(item.get("source_id"))
        if claim and domain and item.get("evidence"):
            groups.setdefault(claim, []).append({**item, "domain": domain})

    agreements, conflicts = [], []
    for claim, items in groups.items():
        independent = {item["domain"] for item in items}
        if len(independent) < 2:
            continue
        normalized = [" ".join(str(item["evidence"]).lower().split()) for item in items]
        negative = any(f"not {claim}" in value or f"no {claim}" in value for value in normalized)
        positive = any(claim in value and f"not {claim}" not in value and f"no {claim}" not in value for value in normalized)
        record = {"claim": items[0]["claim"], "source_ids": [item["source_id"] for item in items]}
        if negative and positive:
            conflicts.append(record)
        elif len(set(normalized)) == 1:
            agreements.append(record)

    if conflicts:
        status = "CONFLICT"
    elif agreements:
        status = "AGREEMENT"
    else:
        status = "INSUFFICIENT_EVIDENCE"
    return {"status": status, "agreements": agreements, "conflicts": conflicts,
            "insufficient_evidence": status == "INSUFFICIENT_EVIDENCE"}


def validate_citations(sources: list[dict], evidence: list[dict]) -> list[dict]:
    by_id = {item.get("id"): item for item in sources}
    citations = []
    for item in evidence:
        source = by_id.get(item.get("source_id"))
        if not source or not _canonical_url(str(source.get("url") or "")) or not item.get("evidence"):
            continue
        citations.append({"source_id": source["id"], "url": source["url"],
                          "title": source["title"], "domain": source["domain"],
                          "claim_ids": [source["id"]]})
    return citations


def classify_intent(question: str) -> ResearchPlan:
    value = question.strip().lower()
    current = any(token in value for token in ("latest", "today", "current", "news", "price", "recent"))
    comparison = any(token in value for token in ("compare", "best ", "versus", " vs "))
    if current:
        return ResearchPlan("CURRENT_INFORMATION", True, 4, 2)
    if comparison:
        return ResearchPlan("COMPARISON", True, 4, 2)
    if any(token in value for token in ("research", "sources", "evidence")):
        return ResearchPlan("RESEARCH", True, 5, 2)
    if any(token in value for token in ("calculate", "solve", "equation")):
        return ResearchPlan("MATHEMATICAL", False, 0, 0)
    return ResearchPlan("EXPLANATION", False, 0, 0)


def _canonical_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        return None
    try:
        if not _is_public_address(ipaddress.ip_address(host)):
            return None
    except ValueError:
        pass
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


class ResearchProvider(ABC):
    """Normalized boundary for real, configured research providers."""

    name: str
    latency_rank: int = 100

    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, limit: int) -> list[dict]:
        raise NotImplementedError


class TavilySearchProvider(ResearchProvider):
    name = "tavily"
    latency_rank = 10

    def configured(self) -> bool:
        return bool(current_app.config.get("TAVILY_API_KEY"))

    def search(self, query: str, limit: int) -> list[dict]:
        if not self.configured():
            raise ResearchUnavailable("RESEARCH_PROVIDER_NOT_CONFIGURED")
        timeout = current_app.config.get("RESEARCH_HTTP_TIMEOUT_SECONDS", 8)
        response = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": current_app.config["TAVILY_API_KEY"], "query": query, "max_results": limit},
            timeout=timeout,
        )
        response.raise_for_status()
        results, seen = [], set()
        for item in response.json().get("results", []):
            url = _canonical_url(str(item.get("url") or ""))
            if not url or url in seen:
                continue
            seen.add(url)
            results.append({"id": f"web-{len(results) + 1}", "url": url, "canonical_url": url,
                            "title": str(item.get("title") or url)[:300],
                            "snippet": str(item.get("content") or "")[:1200],
                            "domain": urlsplit(url).hostname, "provider": self.name,
                            "retrieved_at": datetime.now(timezone.utc).isoformat()})
            if len(results) >= limit:
                break
        return results


def capability() -> dict:
    provider = TavilySearchProvider()
    configured = provider.configured()
    # Configuration is not a provider health check.  Do not announce ACTIVE
    # until a request has actually succeeded in the current operation.
    return {"id": "search.web", "status": "CONFIGURED" if configured else "NOT_CONFIGURED",
            "configured": configured, "enabled": configured, "provider": provider.name if configured else None}


def select_research_provider(plan: ResearchPlan) -> ResearchProvider:
    """Choose one suitable configured provider; never fan out implicitly."""
    providers: list[ResearchProvider] = [TavilySearchProvider()]
    configured = [provider for provider in providers if provider.configured()]
    if not configured:
        raise ResearchUnavailable("RESEARCH_PROVIDER_NOT_CONFIGURED")
    return min(configured, key=lambda provider: provider.latency_rank)


def research(question: str, requested: bool) -> tuple[ResearchPlan, list[dict]]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("RESEARCH_QUERY_INVALID")
    if len(question) > current_app.config.get("RESEARCH_QUERY_MAX_CHARS", 2_000):
        raise ValueError("RESEARCH_QUERY_TOO_LARGE")
    plan = classify_intent(question)
    if not requested:
        return plan, []
    provider = select_research_provider(plan)
    try:
        sources = provider.search(question, plan.max_sources or 3)
    except requests.RequestException as error:
        current_app.logger.warning("Research provider failed category=UPSTREAM_UNAVAILABLE")
        raise ResearchProviderError("RESEARCH_PROVIDER_UNAVAILABLE") from error
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        current_app.logger.warning("Research provider failed category=INVALID_RESPONSE")
        raise ResearchProviderError("RESEARCH_PROVIDER_INVALID_RESPONSE") from error
    fetch_budget = min(
        plan.max_parallel_requests,
        max(0, current_app.config.get("RESEARCH_FETCH_MAX_SOURCES", 2)),
    )
    if fetch_budget:
        max_bytes = current_app.config.get("RESEARCH_FETCH_MAX_BYTES", 200_000)
        max_chars = current_app.config.get("RESEARCH_FETCH_MAX_CHARS", 12_000)
        http_timeout = current_app.config.get("RESEARCH_HTTP_TIMEOUT_SECONDS", 8)

        def fetch_one(source):
            try:
                return fetch_evidence(
                    source, max_bytes=max_bytes, max_chars=max_chars, timeout=http_timeout,
                ), "COMPLETED", None
            except ResearchFetchBlocked:
                return None, "BLOCKED", "RESEARCH_FETCH_BLOCKED"
            except (requests.RequestException, ValueError):
                return None, "FAILED", "RESEARCH_FETCH_FAILED"

        selected = sources[:fetch_budget]
        with ThreadPoolExecutor(max_workers=fetch_budget, thread_name_prefix="research-fetch") as executor:
            outcomes = list(executor.map(fetch_one, selected))
        for source, (evidence, status, category) in zip(selected, outcomes):
            source["fetch_status"] = status
            if evidence:
                source["fetched_evidence"] = evidence
            if category:
                current_app.logger.warning(
                    "Research evidence fetch did not complete category=%s source_id=%s",
                    category, source["id"],
                )
    return plan, sources
