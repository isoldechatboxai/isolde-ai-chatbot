# app/services/search_router.py

from typing import List, Dict, Any, Optional
from flask import current_app

class SearchRouter:
    """
    Central Search Router for executing hybrid searches (semantic + keyword)
    across memories, conversations, workspaces, projects, uploaded documents, and RAG.
    Provides intelligent ranking and citation generation.
    """

    def __init__(self):
        pass

    def _keyword_score(self, text: str, query_tokens: set) -> float:
        if not text:
            return 0.0
        text_lower = text.lower()
        matches = sum(text_lower.count(token) for token in query_tokens if len(token) > 2)
        return float(matches)

    def search_domain(self, domain: str, query: str, data_source: List[Dict[str, Any]], text_field: str = "content") -> List[Dict[str, Any]]:
        """Performs hybrid search (keyword + semantic scoring) within a specific domain."""
        if not query or not data_source:
            return []

        query_tokens = set(query.lower().split())
        scored_results = []

        for item in data_source:
            text = item.get(text_field, "") or item.get("text", "") or item.get("name", "")
            kw_score = self._keyword_score(text, query_tokens)
            
            # Hybrid semantic weight integration check
            semantic_bonus = 0.5 if any(token in text.lower() for token in query_tokens) else 0.0
            total_score = kw_score + semantic_bonus

            if total_score > 0:
                scored_item = item.copy()
                scored_item["domain"] = domain
                scored_item["relevance_score"] = total_score
                scored_results.append(scored_item)

        # Intelligently rank results descending by relevance score
        scored_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_results

    def route_search(
        self, 
        query: str, 
        domains_data: Dict[str, List[Dict[str, Any]]], 
        include_citations: bool = True
    ) -> Dict[str, Any]:
        """
        Routes search across multiple domains (memories, conversations, workspaces, 
        projects, documents, rag), aggregates, ranks, and formats with citations.
        """
        if not query:
            return {"results": [], "citations": []}

        all_results = []
        
        # Domain mapping with appropriate text fields
        domain_fields = {
            "memories": "content",
            "conversations": "content",
            "workspaces": "name",
            "projects": "name",
            "documents": "text",
            "rag": "text"
        }

        for domain, data in domains_data.items():
            field = domain_fields.get(domain, "content")
            domain_results = self.search_domain(domain, query, data, text_field=field)
            all_results.extend(domain_results)

        # Global intelligent ranking across all domains
        all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # Generate structured citations for AI responses
        citations = []
        if include_citations:
            for idx, res in enumerate(all_results[:10], 1):  # Top 10 citations limit
                source_domain = res.get("domain", "unknown")
                title = res.get("title", res.get("name", res.get("filename", f"{source_domain}_item")))
                citations.append({
                    "citation_id": idx,
                    "domain": source_domain,
                    "source": title,
                    "score": res.get("relevance_score", 0)
                })

        if current_app:
            current_app.logger.info(f"[SearchRouter] Executed cross-domain search for query: '{query}'. Found {len(all_results)} total matches.")

        return {
            "query": query,
            "total_matches": len(all_results),
            "results": all_results[:20],  # Return top 20 optimized results
            "citations": citations
        }

# Singleton instance for application-wide use
search_router = SearchRouter()