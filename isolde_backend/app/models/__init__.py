"""
Isolde backend — models package initializer.

This module imports all model modules so that SQLAlchemy registers every
mapper with the shared metadata BEFORE configure_mappers() runs.

This ensures string-based relationships such as:

    db.relationship("Conversation", ...)

can resolve successfully.

All Flask application wiring (create_app, JWT, CORS, blueprints, routes,
middleware, db.create_all) belongs in app/__init__.py — NOT here.
"""

# ---------------------------------------------------------------------------
# Import each model module to register its mapper(s) with SQLAlchemy.
#
# The import order matters: models that are referenced by string-based
# relationships in OTHER models must be imported so their class is registered
# in the mapper registry. Importing the module is sufficient — we do not
# need to reference the classes directly unless we want to re-export them.
# ---------------------------------------------------------------------------

# Core user and conversation models (User has relationship to Conversation)
from app.models.user import User
from app.models.conversation import Conversation

# API key models (two separate systems)
from app.models.api_key_model import ApiKey
from app.models.saas_cloud_model import Tenant, Subscription, Invoice, APIKey

# All remaining model modules — imported to ensure their mappers register.
# Each import triggers SQLAlchemy to register the db.Model subclasses
# defined in that module.
import app.models.ai_studio_model
import app.models.analytics_model
import app.models.billing_model
import app.models.chat_extended_models
import app.models.collaboration_model
import app.models.enterprise_models
import app.models.feedback
import app.models.intelligence_model
import app.models.marketplace_model
import app.models.memory_model
import app.models.plugin_model
import app.models.productivity_model
import app.models.uploaded_file
import app.models.voice_model
import app.models.workflow_model
import app.models.workspace_model


__all__ = [
    "User",
    "Conversation",
    "ApiKey",
    "Tenant",
    "Subscription",
    "Invoice",
    "APIKey",
]