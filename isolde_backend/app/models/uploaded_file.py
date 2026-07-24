import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid():
    return str(uuid.uuid4())


class UploadedFile(db.Model):
    __tablename__ = "uploaded_files"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    extracted_chars = db.Column(db.Integer, default=0)
    indexed = db.Column(db.Boolean, default=False)  # whether added to vector store
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "extracted_chars": self.extracted_chars,
            "indexed": self.indexed,
            "created_at": self.created_at.isoformat(),
        }
