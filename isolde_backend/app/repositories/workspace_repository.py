from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.workspace import Workspace  # Assuming model exists

class WorkspaceRepository:
    """
    Repository dedicated solely to Workspace data operations.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, workspace_id: str) -> Optional[Workspace]:
        return self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

    def get_user_workspaces(self, user_id: int) -> List[Workspace]:
        return self.db.query(Workspace).filter(Workspace.user_id == user_id).all()

    def create(self, data: dict) -> Workspace:
        workspace = Workspace(**data)
        self.db.add(workspace)
        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def update(self, workspace: Workspace, data: dict) -> Workspace:
        for key, value in data.items():
            setattr(workspace, key, value)
        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def delete(self, workspace_id: str) -> bool:
        workspace = self.get_by_id(workspace_id)
        if workspace:
            self.db.delete(workspace)
            self.db.commit()
            return True
        return False