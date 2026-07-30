# app/services/conversation_analyzer.py

from typing import List, Dict, Any, Optional
from flask import current_app

class ConversationAnalyzer:
    """
    Analyzes conversation history, detects user intent, and extracts key insights
    to enhance contextual relevance and memory intelligence.
    """

    def __init__(self):
        # Define common intent categories and keywords for heuristic detection
        self.intent_keywords = {
            "coding": ["code", "bug", "error", "python", "flask", "function", "api", "script", "import"],
            "business": ["price", "margin", "profit", "business", "cost", "sales", "revenue", "product", "brand"],
            "analysis": ["analyze", "report", "data", "summary", "metrics", "performance", "track"],
            "query": ["what", "how", "why", "where", "when", "can you", "explain", "help"]
        }

    def detect_intent(self, query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Detects the primary intent of the user based on the current query and history.
        """
        if not query:
            return "general"

        query_lower = query.lower()
        scores = {intent: 0 for intent in self.intent_keywords}
        
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in query_lower:
                    scores[intent] += 1

        best_intent = max(scores, key=scores.get)
        if scores[best_intent] == 0:
            return "general"

        return best_intent

    def analyze_conversation(self, chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyzes a sequence of conversation turns to extract overall intent trends
        and metrics for context optimization.
        """
        if not chat_history:
            return {"message_count": 0, "dominant_intent": "general", "summary_hint": "No history available."}

        intents = []
        for message in chat_history:
            if message.get("role") == "user":
                content = message.get("content", "")
                intents.append(self.detect_intent(content))

        dominant_intent = max(set(intents), key=intents.count) if intents else "general"

        if current_app:
            current_app.logger.info(f"[ConversationAnalyzer] Analyzed {len(chat_history)} messages. Dominant intent: {dominant_intent}")

        return {
            "message_count": len(chat_history),
            "dominant_intent": dominant_intent,
            "intents_history": intents,
            "summary_hint": f"Conversation contains {len(chat_history)} messages focusing primarily on {dominant_intent}."
        }

# Singleton instance for application-wide use
conversation_analyzer = ConversationAnalyzer()