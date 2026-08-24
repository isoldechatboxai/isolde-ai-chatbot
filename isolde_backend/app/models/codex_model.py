"""
Isolde backend — Codex Project Engineering Models.
Provides strict workspace boundaries for project-level AI code generation.
"""
from datetime import datetime
from typing import Optional
from app.extensions import db


class CodexProject(db.Model):
    """
    Represents a Codex engineering project.
    Strictly owned by a user (or workspace).
    """
    __tablename__ = "codex_projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Project state
    status = db.Column(db.String(50), default="Active", nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    files = db.relationship(
        "CodexProjectFile",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan"
    )
    tasks = db.relationship(
        "CodexTask",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "file_count": len(self.files) if self.files else 0,
            "task_count": len(self.tasks) if self.tasks else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CodexProjectFile(db.Model):
    """
    Represents a file within a Codex project.
    SECURITY: Path is relative to the project root. Absolute paths are rejected at the service layer.
    """
    __tablename__ = "codex_project_files"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("codex_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    file_path = db.Column(db.String(500), nullable=False)
    file_content = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    
    # Versioning / Audit
    version = db.Column(db.Integer, default=1, nullable=False)
    last_modified_by = db.Column(db.String(255), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Composite unique constraint: one file path per project
    __table_args__ = (
        db.UniqueConstraint('project_id', 'file_path', name='uq_project_file_path'),
    )

    def to_dict(self, include_content: bool = False) -> dict:
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "version": self.version,
            "last_modified_by": self.last_modified_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            data["file_content"] = self.file_content
        return data


class CodexTask(db.Model):
    """
    Represents an engineering task or instruction within a project.
    Tracks the AI's plan, execution status, and validation results.
    """
    __tablename__ = "codex_tasks"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("codex_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    instruction = db.Column(db.Text, nullable=False)
    ai_plan = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(50), default="pending", nullable=False)
    validation_output = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "instruction": self.instruction,
            "ai_plan": self.ai_plan,
            "status": self.status,
            "validation_output": self.validation_output,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }