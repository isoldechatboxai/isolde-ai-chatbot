# app/models/__init__.py
# All SQLAlchemy models must be imported here to ensure db.create_all() registers them

from app.models.user import User, Setting, PromoCode, Broadcast
from app.models.conversation import Conversation, Message
from app.models.feedback import Feedback
from app.models.uploaded_file import UploadedFile

# Billing models
from app.models.billing_model import Subscription, CreditBalance, Invoice

# Memory model
from app.models.memory_model import UserMemory

# Chat extended models (folders, tags, bookmarks, reactions, analytics)
from app.models.chat_extended_models import (
    ChatFolder,
    ChatTag,
    ConversationTagMap,
    PinnedChat,
    MessageReaction,
    Bookmark,
    ConversationAnalytics
)

# Workspace models
from app.models.workspace_model import Workspace, Project, Agent, WorkspaceDocument

# Voice models
from app.models.voice_model import VoiceProfile, AudioSettings, VoiceSession, Meeting, Speaker, Transcript

# Workflow models
from app.models.workflow_model import Workflow, WorkflowExecution

# Collaboration models
from app.models.collaboration_model import Organization, OrganizationRole, OrganizationMember, Team, Invitation

# Marketplace models
from app.models.marketplace_model import Developer, Plugin, PluginInstallation

# SaaS Cloud models
from app.models.saas_cloud_model import Tenant, Subscription, Invoice, APIKey

# Intelligence models
from app.models.intelligence_model import AIInsight, Recommendation, LearningProfile

# Productivity models
from app.models.productivity_model import Task, Note, CalendarEvent, Bookmark

# Plugin model
from app.models.plugin_model import CustomPlugin

# AI Studio model
from app.models.ai_studio_model import CustomModel, PlaygroundRun

# API Key model
from app.models.api_key_model import ApiKey

# Analytics model
from app.models.analytics_model import AnalyticsModel

# Enterprise models
from app.models.enterprise_models import PromptVersion, TokenCostLog, ScoredMemory, AuditLog

__all__ = [
    # Core models
    "User", "Setting", "PromoCode", "Broadcast",
    "Conversation", "Message",
    "Feedback",
    "UploadedFile",
    
    # Billing
    "Subscription", "CreditBalance", "Invoice",
    
    # Memory
    "UserMemory",
    
    # Chat extended
    "ChatFolder", "ChatTag", "ConversationTagMap", "PinnedChat",
    "MessageReaction", "Bookmark", "ConversationAnalytics",
    
    # Workspace
    "Workspace", "Project", "Agent", "WorkspaceDocument",
    
    # Voice
    "VoiceProfile", "AudioSettings", "VoiceSession", "Meeting", "Speaker", "Transcript",
    
    # Workflow
    "Workflow", "WorkflowExecution",
    
    # Collaboration
    "Organization", "OrganizationRole", "OrganizationMember", "Team", "Invitation",
    
    # Marketplace
    "Developer", "Plugin", "PluginInstallation",
    
    # SaaS Cloud
    "Tenant", "Subscription", "Invoice", "APIKey",
    
    # Intelligence
    "AIInsight", "Recommendation", "LearningProfile",
    
    # Productivity
    "Task", "Note", "CalendarEvent", "Bookmark",
    
    # Plugin
    "CustomPlugin",
    
    # AI Studio
    "CustomModel", "PlaygroundRun",
    
    # API Key
    "ApiKey",
    
    # Analytics
    "AnalyticsModel",
    
    # Enterprise
    "PromptVersion", "TokenCostLog", "ScoredMemory", "AuditLog",
]
