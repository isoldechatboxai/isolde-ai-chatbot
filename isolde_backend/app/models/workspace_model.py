# app/models/workspace_model.py
from datetime import datetime
from typing import Optional
from app import db


class Workspace(db.Model):
    """
    Top-level container for a team/organization's AI workspace.
    A workspace groups Projects, Agents, and shared Documents together.
    """
    __tablename__ = "workspaces"

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: str = db.Column(db.String(255), nullable=False, index=True)
    name: str = db.Column(db.String(255), nullable=False)
    description: Optional[str] = db.Column(db.Text, nullable=True)
    is_active: bool = db.Column(db.Boolean, default=True, nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships (cascade delete keeps DB consistent when a workspace is removed)
    projects = db.relationship(
        "Project", backref="workspace", lazy=True, cascade="all, delete-orphan"
    )
    agents = db.relationship(
        "Agent", backref="workspace", lazy=True, cascade="all, delete-orphan"
    )
    documents = db.relationship(
        "WorkspaceDocument", backref="workspace", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "project_count": len(self.projects) if self.projects else 0,
            "agent_count": len(self.agents) if self.agents else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Project(db.Model):
    """
    A project lives inside a Workspace. Used to scope conversations/documents
    to a specific initiative (e.g. "Q3 Marketing Plan").
    """
    __tablename__ = "projects"

    id: int = db.Column(db.Integer, primary_key=True)
    workspace_id: int = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: str = db.Column(db.String(255), nullable=False)
    description: Optional[str] = db.Column(db.Text, nullable=True)
    status: str = db.Column(db.String(50), default="Active", nullable=False)  # Active, Archived, Completed
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    documents = db.relationship(
        "WorkspaceDocument", backref="project", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "document_count": len(self.documents) if self.documents else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Agent(db.Model):
    """
    An AI Agent is a configured persona/system-prompt bound to a Workspace.
    Users can switch between Agents instantly; the active agent's system_prompt
    is injected into the AI call context (see provider_router.py integration).
    """
    __tablename__ = "agents"

    id: int = db.Column(db.Integer, primary_key=True)
    workspace_id: int = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: str = db.Column(db.String(255), nullable=False)
    role_description: Optional[str] = db.Column(db.String(255), nullable=True)  # e.g. "Sales Assistant"
    system_prompt: str = db.Column(db.Text, nullable=False)
    avatar_emoji: str = db.Column(db.String(10), default="🤖", nullable=False)
    is_default: bool = db.Column(db.Boolean, default=False, nullable=False)
    is_active: bool = db.Column(db.Boolean, default=True, nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "role_description": self.role_description,
            "system_prompt": self.system_prompt,
            "avatar_emoji": self.avatar_emoji,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkspaceDocument(db.Model):
    """
    A document uploaded/attached at Workspace or Project level.
    project_id is nullable: a document can belong to the whole Workspace
    (shared knowledge) or be scoped to one specific Project.
    """
    __tablename__ = "workspace_documents"

    id: int = db.Column(db.Integer, primary_key=True)
    workspace_id: int = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True
    )
    project_id: Optional[int] = db.Column(
        db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True
    )
    file_name: str = db.Column(db.String(255), nullable=False)
    file_type: Optional[str] = db.Column(db.String(50), nullable=True)  # pdf, docx, txt, etc.
    extracted_text: Optional[str] = db.Column(db.Text, nullable=True)  # raw text used for RAG
    uploaded_by: Optional[str] = db.Column(db.String(255), nullable=True)  # user_id
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "uploaded_by": self.uploaded_by,
            "has_extracted_text": bool(self.extracted_text),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }