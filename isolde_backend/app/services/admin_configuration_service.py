from urllib.parse import urlparse

from app.extensions import db
from app.models.user import Setting


FEATURE_DEFAULTS = {
    "ai_studio": True, "workflows": True, "files_rag": True,
    "billing": True, "organization": True, "image": True,
    "video": True, "marketplace": False, "voice": True,
    "collaboration": True,
}

BRANDING_DEFAULTS = {
    "application_name": "Isolde AI",
    "short_description": "Your intelligent AI workspace",
    "footer_text": "Isolde AI can make mistakes. Please verify important information.",
    "support_url": "",
    "announcement": "",
}

BRANDING_LIMITS = {
    "application_name": 80, "short_description": 240,
    "footer_text": 300, "support_url": 500, "announcement": 500,
}

BUNDLED_ASSETS = {
    "logo": "/images/isolde-logo.png",
    "app_icon": "/images/isolde-orb.png",
    "dark_logo": "/images/isolde-logo.png",
    "light_logo": "/images/isolde-logo.png",
    "status": "BUNDLED",
    "upload_status": "NOT_CONFIGURED",
}


def _setting_map():
    rows = Setting.query.filter(
        db.or_(Setting.key.like("feature.%"), Setting.key.like("branding.%"))
    ).all()
    return {item.key: item.value for item in rows}


def public_configuration():
    values = _setting_map()
    features = {
        name: str(values.get(f"feature.{name}", str(default))).lower() == "true"
        for name, default in FEATURE_DEFAULTS.items()
    }
    branding = {
        name: values.get(f"branding.{name}", default)
        for name, default in BRANDING_DEFAULTS.items()
    }
    return {"features": features, "branding": branding, "assets": BUNDLED_ASSETS}


def _save(key, value):
    row = Setting.query.filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))


def update_configuration(data):
    if not isinstance(data, dict):
        raise ValueError("Configuration payload must be an object.")
    changed = []
    features = data.get("features", {})
    if not isinstance(features, dict):
        raise ValueError("features must be an object.")
    for name, value in features.items():
        if name not in FEATURE_DEFAULTS or not isinstance(value, bool):
            raise ValueError(f"Invalid feature flag: {name}.")
        _save(f"feature.{name}", "true" if value else "false")
        changed.append(f"feature.{name}")

    branding = data.get("branding", {})
    if not isinstance(branding, dict):
        raise ValueError("branding must be an object.")
    for name, value in branding.items():
        if name not in BRANDING_DEFAULTS or not isinstance(value, str):
            raise ValueError(f"Invalid branding field: {name}.")
        value = value.strip()
        if len(value) > BRANDING_LIMITS[name] or "<" in value or ">" in value:
            raise ValueError(f"Invalid branding value: {name}.")
        if name == "support_url" and value:
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("support_url must be an absolute HTTPS URL.")
        _save(f"branding.{name}", value)
        changed.append(f"branding.{name}")

    if not changed:
        raise ValueError("No supported configuration values supplied.")
    return changed
