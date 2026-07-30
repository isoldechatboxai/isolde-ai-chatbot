# app/services/context_ranker.py

from typing import List, Dict, Any
from flask import current_app

class ContextRanker:
    """
    Ranks retrieved memories and document knowledge chunks by relevance 
    to the current user query, ensuring only the highest-value context is used.
    """

    def rank_items(self, query: str, items: List[Dict[str, Any]], text_key: str = "content") -> List[Dict[str, Any]]:
        """
        Scores and ranks a list of items (memories or chunks) based on keyword matching 
        and term frequency relative to the query.
        """
        if not query or not items:
            return items

        query_tokens = set(query.lower().split())
        scored_items = []

        for item in items:
            # Extract text safely from dict or string
            if isinstance(item, dict):
                text = item.get(text_key, "") or item.get("text", "")
            else:
                text = str(item)
                item = {"content": text}

            text_lower = text.lower()
            score = 0

            # Calculate simple relevance score based on token intersection
            for token in query_tokens:
                if len(token) > 2:  # Ignore tiny stop words
                    if token in text_lower:
                        score += text_lower.count(token)

            # Assign score to item copy
            scored_item = item.copy()
            scored_item["relevance_score"] = score
            scored_items.append(scored_item)

        # Sort items descending by relevance score
        ranked_items = sorted(scored_items, key=lambda x: x.get("relevance_score", 0), reverse=True)

        if current_app:
            current_app.logger.info(f"[ContextRanker] Ranked {len(items)} items based on query relevance.")

        return ranked_items

# Singleton instance for application-wide use
context_ranker = ContextRanker()