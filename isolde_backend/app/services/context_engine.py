# app/services/context_engine.py

from typing import List, Dict, Any, Optional
from flask import current_app

# Import existing services safely with fallbacks
try:
    from app.services.memory_service import get_user_memories
except ImportError:
    def get_user_memories(user_id): return []

try:
    from app.services.history_service import get_chat_history
except ImportError:
    def get_chat_history(user_id, limit=5): return []

try:
    from app.services.rag_service import search_similar_chunks
except ImportError:
    def search_similar_chunks(query, user_id=None, limit=3): return []

class ContextEngine:
    """
    Aggregates and assembles context from multiple sources:
    Memory, Chat History, Workspace, Uploaded Files, and RAG.
    """

    def assemble_context(self, user_id: str, query: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Gathers context fragments from all available data layers for a given user query.
        """
        context_fragments = []
        chat_history = []

        try:
            # 1. Fetch relevant user memories
            memories = get_user_memories(user_id) if callable(get_user_memories) else []
            if memories:
                for mem in memories[:5]: # Limit to top 5
                    content = mem.get("content") if isinstance(mem, dict) else str(mem)
                    context_fragments.append(f"[User Memory]: {content}")

            # 2. Fetch RAG / Vector search snippets based on query
            if query:
                rag_results = search_similar_chunks(query, user_id=user_id, limit=3) if callable(search_similar_chunks) else []
                for chunk in rag_results:
                    text = chunk.get("text") if isinstance(chunk, dict) else str(chunk)
                    filename = chunk.get("filename", "document")
                    context_fragments.append(f"[Document Knowledge ({filename})]: {text}")

            # 3. Fetch recent conversation history
            history_raw = get_chat_history(user_id, limit=6) if callable(get_chat_history) else []
            for h in history_raw:
                if isinstance(h, dict):
                    chat_history.append({
                        "role": h.get("role", "user"),
                        "content": h.get("content", "")
                    })

        except Exception as e:
            if current_app:
                current_app.logger.error(f"[ContextEngine] Error assembling context for user {user_id}: {str(e)}")

        return {
            "context_fragments": context_fragments,
            "chat_history": chat_history,
            "workspace_id": workspace_id
        }

# Singleton instance for application-wide use
context_engine = ContextEngine()