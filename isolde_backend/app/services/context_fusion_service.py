# app/services/context_fusion_service.py

from typing import List, Dict, Any, Optional
from flask import current_app
from app.services.conversation_analyzer import conversation_analyzer
from app.services.context_ranker import context_ranker

class ContextFusionService:
    """
    Fuses multiple context sources (memories, RAG documents, chat history, 
    and user preferences) into a single optimized context payload.
    """

    def fuse_context(
        self, 
        user_id: str, 
        query: str, 
        memories: List[Dict[str, Any]], 
        documents: List[Dict[str, Any]], 
        chat_history: List[Dict[str, str]],
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyzes intent, ranks fragments, trims history, 
        and fuses everything into an optimized context package.
        """
        try:
            # 1. Detect Intent and Analyze Conversation
            intent_analysis = conversation_analyzer.analyze_conversation(chat_history)
            
            # 2. Rank Memories and Documents by Relevance
            ranked_memories = context_ranker.rank_items(query, memories, text_key="content")
            ranked_docs = context_ranker.rank_items(query, documents, text_key="text")

            # 3. Build optimized context fragments
            fused_fragments = []

            # Add top ranked memories (limit to top 3)
            for mem in ranked_memories[:3]:
                score = mem.get("relevance_score", 0)
                content = mem.get("content", "")
                fused_fragments.append(f"[Relevant Memory (Score: {score})]: {content}")

            # Add top ranked documents (limit to top 3)
            for doc in ranked_docs[:3]:
                score = doc.get("relevance_score", 0)
                text = doc.get("text", "")
                filename = doc.get("filename", "document")
                fused_fragments.append(f"[Document Knowledge - {filename} (Score: {score})]: {text}")

            # 4. Apply User Preferences / Personalization hints if available
            if user_preferences:
                pref_str = ", ".join([f"{k}: {v}" for k, v in user_preferences.items()])
                fused_fragments.append(f"[User Preferences & Style]: {pref_str}")

            if current_app:
                current_app.logger.info(f"[ContextFusion] Successfully fused context for user {user_id}. Dominant intent: {intent_analysis.get('dominant_intent')}")

            return {
                "intent_analysis": intent_analysis,
                "fused_fragments": fused_fragments,
                "chat_history": chat_history[-5:] if chat_history else []  # Keep recent history trimmed for token efficiency
            }

        except Exception as e:
            if current_app:
                current_app.logger.error(f"[ContextFusion] Error fusing context: {str(e)}")
            return {
                "intent_analysis": {"dominant_intent": "general"},
                "fused_fragments": [],
                "chat_history": chat_history or []
            }

# Singleton instance for application-wide use
context_fusion_service = ContextFusionService()