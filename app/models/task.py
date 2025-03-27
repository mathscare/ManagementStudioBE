from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import enum

class RecurrenceType(str, enum.Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class TaskStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

class TaskStep(BaseModel):
    id: Optional[UUID] = Field(default=None)
    task_id: UUID
    order: int
    content_type: str
    content: str
    attachments: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SubTask(BaseModel):
    id: Optional[UUID] = Field(default=None)
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    attachments: str = ""
    parent_task_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class Task(BaseModel):
    id: Optional[UUID] = Field(default=None)
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    due_date: Optional[datetime] = None
    recurrence_type: RecurrenceType = RecurrenceType.NONE
    recurrence_config: Optional[Dict[str, Any]] = None
    attachments: Optional[List] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tenant_id: UUID
    created_by: UUID
    subtasks: Optional[List[UUID]] = []
    steps: Optional[List[UUID]] = []
    user_assignees: Optional[List[UUID]] = []
    role_assignees: Optional[List[UUID]] = []
