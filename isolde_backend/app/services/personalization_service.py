# app/services/personalization_service.py

from typing import Dict, Any, Optional
from flask import current_app

class PersonalizationService:
    """
    Manages user preferences and injects personalized hints and styling 
    into context and prompts to tailor AI responses.
    """

    def __init__(self):
        self.default_preferences = {
            "tone": "professional",
            "verbosity": "balanced",
            "code_style": "pythonic"
        }

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Retrieves user preferences for profile tailoring."""
        try:
            # Can be integrated with database profile repository
            return self.default_preferences.copy()
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[PersonalizationService] Error fetching preferences for user {user_id}: {str(e)}")
            return self.default_preferences.copy()

    def apply_personalization(self, user_id: str, prompt_context: str) -> str:
        """Injects personalization traits or instructions into the context string."""
        prefs = self.get_user_preferences(user_id)
        tone = prefs.get("tone", "professional")
        verbosity = prefs.get("verbosity", "balanced")
        
        personalization_hint = f"\n[Personalization Guideline]: Adopt a {tone} tone and maintain a {verbosity} response length tailored to user profile."
        
        return prompt_context + personalization_hint

# Singleton instance for application-wide use
personalization_service = PersonalizationService()