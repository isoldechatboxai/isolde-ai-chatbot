from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.workflow import Workflow  # Assuming model exists

class WorkflowRepository:
    """
    Repository dedicated solely to Workflow automation data operations.
    Contains zero business logic.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, workflow_id: str) -> Optional[Workflow]:
        return self.db.query(Workflow).filter(Workflow.id == workflow_id).first()

    def get_user_workflows(self, user_id: int) -> List[Workflow]:
        return self.db.query(Workflow).filter(Workflow.user_id == user_id).all()

    def create(self, data: dict) -> Workflow:
        workflow = Workflow(**data)
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def update(self, workflow: Workflow, data: dict) -> Workflow:
        for key, value in data.items():
            setattr(workflow, key, value)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def delete(self, workflow_id: str) -> bool:
        workflow = self.get_by_id(workflow_id)
        if workflow:
            self.db.delete(workflow)
            self.db.commit()
            return True
        return False