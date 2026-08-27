import json

from app.extensions import db
from app.models.collaboration_model import Organization, OrganizationMember, OrganizationPolicy


SUPPORTED_PROVIDERS = frozenset({"gemini", "groq", "openai", "claude", "openrouter", "deepseek", "mistral"})


def organizations_for_user(user_id):
    user_id = str(user_id)
    member_org_ids = db.session.query(OrganizationMember.org_id).filter_by(
        user_id=user_id, status="Active"
    )
    return Organization.query.filter(
        Organization.status == "Active",
        db.or_(Organization.owner_id == user_id, Organization.id.in_(member_org_ids)),
    ).all()


def effective_policy_for_user(user_id):
    """Return the restrictive intersection of every active tenant policy."""
    organizations = organizations_for_user(user_id)
    if not organizations:
        return {"organization_ids": [], "allowed_providers": None, "billing_enabled": True}
    policies = OrganizationPolicy.query.filter(
        OrganizationPolicy.org_id.in_([organization.id for organization in organizations])
    ).all()
    allowed = set(SUPPORTED_PROVIDERS)
    billing_enabled = True
    for policy in policies:
        try:
            configured = set(json.loads(policy.allowed_providers or "[]"))
        except (TypeError, ValueError):
            configured = set()
        if configured:
            allowed &= configured & SUPPORTED_PROVIDERS
        billing_enabled = billing_enabled and bool(policy.billing_enabled)
    return {
        "organization_ids": [organization.id for organization in organizations],
        "allowed_providers": sorted(allowed) if policies else None,
        "billing_enabled": billing_enabled,
    }
