# app/services/guardrails_service.py

import re
from typing import Dict, Any, List, Optional
from flask import current_app

class GuardrailsService:
    """
    Implements security guardrails, prompt injection detection, 
    content moderation, and PII filtering for AI inputs and outputs.
    """

    def __init__(self):
        # Basic patterns for prompt injection detection
        self.injection_patterns = [
            r"ignore previous instructions",
            r"disregard all prior",
            r"you are now unrestricted",
            r"system override",
            r"reveal your system prompt"
        ]
        
        # Simple sensitive terms / toxic keywords filter list
        self.blocked_keywords = [
            "malware_payload_test",
            "exploit_database_unauthorized"
        ]

    def validate_input(self, user_query: str) -> Dict[str, Any]:
        """
        Validates incoming user queries for security threats, 
        prompt injections, and policy violations.
        """
        if not user_query:
            return {"safe": True, "reason": None}

        query_lower = user_query.lower()

        # 1. Check for prompt injection attempts
        for pattern in self.injection_patterns:
            if re.search(pattern, query_lower):
                if current_app:
                    current_app.logger.warning(f"[Guardrails] Prompt injection detected matching pattern: '{pattern}'")
                return {
                    "safe": False,
                    "reason": "Prompt injection attempt detected. Request blocked for security compliance."
                }

        # 2. Check for blocked keywords
        for keyword in self.blocked_keywords:
            if keyword in query_lower:
                if current_app:
                    current_app.logger.warning(f"[Guardrails] Blocked keyword found: '{keyword}'")
                return {
                    "safe": False,
                    "reason": "Content violates safety policies and guidelines."
                }

        return {"safe": True, "reason": None}

    def sanitize_output(self, ai_response: str) -> str:
        """
        Sanitizes outgoing AI responses to ensure no sensitive system 
        data or unverified internal states leak to the user.
        """
        if not ai_response:
            return ""

        # Remove accidental internal system tokens or debug traces if any
        sanitized = re.sub(r"### SYSTEM DEBUG:.*", "", ai_response, flags=re.IGNORECASE)
        
        return sanitized.strip()

# Singleton instance for application-wide use
guardrails_service = GuardrailsService()