from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.upload import UploadedFile  # Assuming model exists

class UploadRepository:
    """
    Repository dedicated solely to File Upload data operations.
    Contains zero business logic.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, file_id: str) -> Optional[UploadedFile]:
        return self.db.query(UploadedFile).filter(UploadedFile.id == file_id).first()

    def get_user_uploads(self, user_id: int) -> List[UploadedFile]:
        return self.db.query(UploadedFile).filter(UploadedFile.user_id == user_id).all()

    def create(self, data: dict) -> UploadedFile:
        upload_record = UploadedFile(**data)
        self.db.add(upload_record)
        self.db.commit()
        self.db.refresh(upload_record)
        return upload_record

    def delete(self, file_id: str) -> bool:
        record = self.get_by_id(file_id)
        if record:
            self.db.delete(record)
            self.db.commit()
            return True
        return False