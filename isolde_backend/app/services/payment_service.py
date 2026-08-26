import hashlib
import hmac
import json
import time

import requests
from flask import current_app


class PaymentNotConfigured(RuntimeError):
    pass


class StripePaymentProvider:
    def __init__(self, config):
        self.secret = config.get("STRIPE_SECRET_KEY", "")
        self.webhook_secret = config.get("STRIPE_WEBHOOK_SECRET", "")
        self.success_url = config.get("PAYMENT_SUCCESS_URL", "")
        self.cancel_url = config.get("PAYMENT_CANCEL_URL", "")
        self.prices = {
            "Pro": config.get("STRIPE_PRICE_PRO", ""),
            "Enterprise": config.get("STRIPE_PRICE_ENTERPRISE", ""),
        }
        if not self.secret:
            raise PaymentNotConfigured("Payment provider is not configured.")

    def create_checkout(self, user_id, plan):
        price = self.prices.get(plan)
        if not price or not self.success_url or not self.cancel_url:
            raise PaymentNotConfigured("The selected payment plan is not configured.")
        response = requests.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(self.secret, ""), timeout=15,
            data={
                "mode": "subscription", "line_items[0][price]": price,
                "line_items[0][quantity]": 1, "success_url": self.success_url,
                "cancel_url": self.cancel_url, "metadata[user_id]": user_id,
                "metadata[plan]": plan, "subscription_data[metadata][user_id]": user_id,
                "subscription_data[metadata][plan]": plan,
            },
        )
        if not response.ok:
            current_app.logger.error("Payment checkout provider returned HTTP %s.", response.status_code)
            raise RuntimeError("Payment provider rejected checkout creation.")
        payload = response.json()
        if not payload.get("id") or not payload.get("url"):
            raise RuntimeError("Payment provider returned an invalid checkout response.")
        return {"checkout_id": payload["id"], "url": payload["url"]}

    def verify_webhook(self, payload, signature):
        if not self.webhook_secret:
            raise PaymentNotConfigured("Payment webhook is not configured.")
        parts = dict(item.split("=", 1) for item in signature.split(",") if "=" in item)
        timestamp, supplied = parts.get("t"), parts.get("v1")
        if not timestamp or not supplied or abs(time.time() - int(timestamp)) > 300:
            raise ValueError("Invalid webhook signature.")
        expected = hmac.new(
            self.webhook_secret.encode(), timestamp.encode() + b"." + payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("Invalid webhook signature.")
        event = json.loads(payload)
        if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
            raise ValueError("Invalid webhook payload.")
        return event


def get_payment_provider():
    provider = current_app.config.get("PAYMENT_PROVIDER", "").lower()
    if provider != "stripe":
        raise PaymentNotConfigured("Payment provider is not configured.")
    return StripePaymentProvider(current_app.config)
