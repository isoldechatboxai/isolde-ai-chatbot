# app/services/semantic_search_service.py

from typing import List, Dict, Any, Optional
from flask import current_app

class SemanticSearchService:
    """
    Implements cross-domain search and matching across user memories, 
    uploaded documents (RAG chunks), and conversation history.
    """

    def search_all(
        self, 
        user_id: str, 
        query: str, 
        memories: List[Dict[str, Any]], 
        documents: List[Dict[str, Any]], 
        chat_history: List[Dict[str, str]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Performs a unified search across memories, documents, and chat history 
        matching query tokens and returning sorted results.
        """
        if not query:
            return {"memories": [], "documents": [], "conversations": []}

        query_tokens = set(query.lower().split())

        def score_text(text: str) -> int:
            text_lower = text.lower()
            return sum(text_lower.count(token) for token in query_tokens if len(token) > 2)

        # 1. Search Memories
        matched_memories = []
        for mem in memories:
            content = mem.get("content", "")
            score = score_text(content)
            if score > 0:
                item = mem.copy()
                item["match_score"] = score
                matched_memories.append(item)
        matched_memories.sort(key=lambda x: x["match_score"], reverse=True)

        # 2. Search Documents / RAG chunks
        matched_docs = []
        for doc in documents:
            text = doc.get("text", "")
            score = score_text(text)
            if score > 0:
                item = doc.copy()
                item["match_score"] = score
                matched_docs.append(item)
        matched_docs.sort(key=lambda x: x["match_score"], reverse=True)

        # 3. Search Chat History
        matched_chats = []
        for msg in chat_history:
            content = msg.get("content", "")
            score = score_text(content)
            if score > 0:
                item = msg.copy()
                item["match_score"] = score
                matched_chats.append(item)
        matched_chats.sort(key=lambda x: x["match_score"], reverse=True)

        if current_app:
            current_app.logger.info(
                f"[SemanticSearch] Queried across domains for user {user_id}. "
                f"Found {len(matched_memories)} memories, {len(matched_docs)} docs, {len(matched_chats)} chats."
            )

        return {
            "memories": matched_memories,
            "documents": matched_docs,
            "conversations": matched_chats
        }

# Singleton instance for application-wide use
semantic_search_service = SemanticSearchService()