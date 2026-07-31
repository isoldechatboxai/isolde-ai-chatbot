import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("isolde.billing")
logger.setLevel(logging.INFO)


class BillingManager:
    """Manages user subscriptions, credit balances, invoice generation, and payment gateway hooks."""

    def __init__(self) -> None:
        # In-memory mock database for subscriptions & credits
        self._subscriptions: Dict[str, str] = {}
        self._credits: Dict[str, int] = {}

    def assign_subscription(self, user_id: str, plan_name: str) -> Dict[str, Any]:
        """Assigns or upgrades a subscription plan for a user."""
        self._subscriptions[user_id] = plan_name
        logger.info(f"User {user_id} assigned to subscription plan: {plan_name}")
        return {
            "status": "success",
            "user_id": user_id,
            "plan": plan_name,
            "message": f"Successfully subscribed to {plan_name}."
        }

    def get_user_credits(self, user_id: str) -> int:
        """Retrieves available AI generation credits for a user."""
        return self._credits.get(user_id, 100)  # Default 100 free credits

    def deduct_credits(self, user_id: str, amount: int) -> bool:
        """Deducts usage credits from user balance."""
        current = self.get_user_credits(user_id)
        if current >= amount:
            self._credits[user_id] = current - amount
            logger.info(f"Deducted {amount} credits from user {user_id}. Remaining: {self._credits[user_id]}")
            return True
        logger.warning(f"Insufficient credits for user {user_id}. Required: {amount}, Available: {current}")
        return False

    def generate_invoice(self, user_id: str, amount_paid: float, currency: str = "USD") -> Dict[str, Any]:
        """Generates a billing invoice record."""
        logger.info(f"Generating invoice for user {user_id} amounting to {amount_paid} {currency}")
        return {
            "status": "generated",
            "user_id": user_id,
            "amount": amount_paid,
            "currency": currency,
            "invoice_id": f"INV-{user_id[:8]}-2026"
        }


# Global billing manager instance
billing_manager = BillingManager()