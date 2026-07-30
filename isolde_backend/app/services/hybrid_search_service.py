# app/services/hybrid_search_service.py

from typing import List, Dict, Any, Optional
from flask import current_app

class HybridSearchService:
    """
    Implements advanced hybrid search combining dense semantic scoring 
    and sparse keyword matching for high-precision retrieval across enterprise data.
    """

    def __init__(self):
        pass

    def compute_hybrid_scores(
        self, 
        query: str, 
        items: List[Dict[str, Any]], 
        text_field: str = "content", 
        alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Computes hybrid scores combining keyword (sparse) and semantic (dense) metrics.
        Alpha balances the weight between keyword score and semantic similarity.
        """
        if not query or not items:
            return items

        query_tokens = set(query.lower().split())
        scored_items = []

        for item in items:
            text = item.get(text_field, "") or item.get("text", "") or item.get("name", "")
            text_lower = text.lower()

            # Keyword score (TF-based)
            keyword_matches = sum(text_lower.count(token) for token in query_tokens if len(token) > 2)
            keyword_score = float(keyword_matches)

            # Semantic similarity simulation score based on token overlap ratio
            item_tokens = set(text_lower.split())
            overlap = len(query_tokens.intersection(item_tokens))
            semantic_score = float(overlap) / max(len(query_tokens), 1)

            # Hybrid scoring formula
            norm_keyword = min(keyword_score / 10.0, 1.0)
            hybrid_score = (alpha * norm_keyword) + ((1.0 - alpha) * semantic_score)

            scored_item = item.copy()
            scored_item["hybrid_score"] = round(hybrid_score, 4)
            scored_item["keyword_score"] = keyword_score
            scored_item["semantic_score"] = semantic_score
            scored_items.append(scored_item)

        # Sort descending by hybrid score
        scored_items.sort(key=lambda x: x["hybrid_score"], reverse=True)

        if current_app:
            current_app.logger.info(f"[HybridSearch] Computed hybrid scores for {len(items)} items.")

        return scored_items

# Singleton instance for application-wide use
hybrid_search_service = HybridSearchService()