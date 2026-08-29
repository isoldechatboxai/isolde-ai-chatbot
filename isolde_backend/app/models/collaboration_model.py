# app/models/collaboration_model.py
from datetime import datetime
import uuid
from app.extensions import db

class Organization(db.Model):
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String(500), nullable=True)
    owner_id = db.Column(db.String(36), nullable=False, index=True)
    status = db.Column(db.String(50), default='Active') # Active, Suspended, Archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "logo_url": self.logo_url,
            "owner_id": self.owner_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class OrganizationRole(db.Model):
    __tablename__ = 'organization_roles'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(50), nullable=False) # e.g., Admin, Manager, Editor, Viewer
    permissions = db.Column(db.Text, nullable=True) # JSON string array: ["manage_users", "manage_billing", "create_agents"]
    
    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "name": self.name,
            "permissions": self.permissions
        }

class OrganizationMember(db.Model):
    __tablename__ = 'organization_members'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('organization_roles.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(50), default='Active') # Active, Suspended
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "user_id": self.user_id,
            "role_id": self.role_id,
            "status": self.status,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None
        }

class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False) # e.g., Engineering, Sales, HR
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Invitation(db.Model):
    __tablename__ = 'invitations'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, nullable=True)
    token = db.Column(db.String(255), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    status = db.Column(db.String(50), default='Pending') # Pending, Accepted, Rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "email": self.email,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class OrganizationProject(db.Model):
    __tablename__ = "organization_projects"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    shared_by = db.Column(db.String(36), nullable=False)
    access_level = db.Column(db.String(20), nullable=False, default="view")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id, "org_id": self.org_id, "project_id": self.project_id,
            "access_level": self.access_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OrganizationPolicy(db.Model):
    __tablename__ = "organization_policies"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    allowed_providers = db.Column(db.Text, nullable=False, default="[]")
    billing_enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        import json
        try:
            providers = json.loads(self.allowed_providers or "[]")
        except (TypeError, ValueError):
            providers = []
        return {
            "org_id": self.org_id,
            "allowed_providers": providers,
            "billing_enabled": self.billing_enabled,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
