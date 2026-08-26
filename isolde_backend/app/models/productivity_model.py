# app/models/productivity_model.py
from datetime import datetime
from app.extensions import db

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(50), default='Medium') # Low, Medium, High, Urgent
    status = db.Column(db.String(50), default='Pending') # Pending, In Progress, Completed, Archived
    due_date = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(100), default='General')
    assigned_agent = db.Column(db.String(100), nullable=True)
    reminder_time = db.Column(db.String(50), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "due_date": self.due_date,
            "category": self.category,
            "assigned_agent": self.assigned_agent,
            "reminder_time": self.reminder_time,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_type = db.Column(db.String(50), default='Meeting') # Meeting, Deadline, Event, Reminder
    start_time = db.Column(db.String(50), nullable=False)
    end_time = db.Column(db.String(50), nullable=True)
    is_ai_scheduled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "description": self.description,
            "event_type": self.event_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_ai_scheduled": self.is_ai_scheduled,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=True)
    folder = db.Column(db.String(100), default='General')
    tags = db.Column(db.String(255), nullable=True)
    is_pinned = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "title": self.title,
            "content": self.content,
            "folder": self.folder,
            "tags": self.tags,
            "is_pinned": self.is_pinned,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Bookmark(db.Model):
    __tablename__ = 'bookmarks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    target_type = db.Column(db.String(50), default='Chat') # Chat, Project, Document, Memory, File
    target_id = db.Column(db.Integer, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "is_pinned": self.is_pinned,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
