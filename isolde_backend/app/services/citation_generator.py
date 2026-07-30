# app/services/citation_generator.py

from typing import List, Dict, Any, Optional
from flask import current_app

class CitationGenerator:
    """
    Generates structured, verifiable citations from search results,
    RAG documents, and memory sources for AI response attribution.
    """

    def __init__(self):
        pass

    def generate_citations(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transforms raw search or knowledge retrieval results into formal citation blocks.
        """
        if not search_results:
            return []

        citations = []
        for idx, item in enumerate(search_results, 1):
            domain = item.get("domain", "general")
            title = item.get("title", item.get("name", item.get("filename", f"{domain}_reference_{idx}")))
            text_content = item.get("content", "") or item.get("text", "")
            snippet = (text_content[:150] + "...") if text_content else ""
            
            citations.append({
                "citation_id": idx,
                "domain": domain,
                "title": title,
                "snippet": snippet,
                "relevance_score": item.get("relevance_score", item.get("hybrid_score", 0.0))
            })

        if current_app:
            current_app.logger.info(f"[CitationGenerator] Generated {len(citations)} structured citations.")

        return citations

    def format_citations_markdown(self, citations: List[Dict[str, Any]]) -> str:
        """Formats citations into a clean Markdown reference block for LLM appending."""
        if not citations:
            return ""

        md_lines = ["\n### References & Sources:"]
        for cite in citations:
            md_lines.append(f"[{cite['citation_id']}] **{cite['title']}** ({cite['domain'].capitalize()}) - Score: {cite['relevance_score']}")

        return "\n".join(md_lines)

# Singleton instance for application-wide use
citation_generator = CitationGenerator()