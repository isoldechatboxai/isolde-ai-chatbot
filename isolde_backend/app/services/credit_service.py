from math import ceil

from app.extensions import db
from app.models.billing_model import CreditBalance, CreditLedger


def deduct_authoritative_usage(user_id, provider_tokens, idempotency_key, tokens_per_credit=1000):
    """Deduct credits once from trusted provider usage metadata."""
    if not isinstance(provider_tokens, int) or provider_tokens < 0:
        raise ValueError("Provider token usage must be a non-negative integer.")
    if not idempotency_key:
        raise ValueError("An idempotency key is required.")
    existing = CreditLedger.query.filter_by(idempotency_key=idempotency_key).with_for_update().first()
    if existing:
        return -existing.credits_delta
    charge = ceil(provider_tokens / max(tokens_per_credit, 1)) if provider_tokens else 0
    balance = CreditBalance.query.filter_by(user_id=str(user_id)).with_for_update().first()
    if not balance:
        balance = CreditBalance(user_id=str(user_id), credits=100)
        db.session.add(balance)
        db.session.flush()
    charged = min(balance.credits, charge)
    balance.credits -= charged
    db.session.add(CreditLedger(
        user_id=str(user_id), idempotency_key=idempotency_key,
        credits_delta=-charged, source="provider_usage", provider_tokens=provider_tokens,
    ))
    return charged
