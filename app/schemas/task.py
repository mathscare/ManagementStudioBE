from pydantic import BaseModel, Field, HttpUrl, BeforeValidator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID

# Enums
class RecurrenceType(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class TaskStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"

# Base schemas
class TaskStepBase(BaseModel):
    order: int
    content_type: ContentType
    content: str
    attachments: Optional[List[str]] = []

class TaskStepCreate(TaskStepBase):
    pass

class TaskStep(TaskStepBase):
    id: UUID
    task_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

class SubTaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    attachments: Optional[List[str]] = []

class SubTaskCreate(SubTaskBase):
    pass

class SubTask(SubTaskBase):
    id: UUID
    parent_task_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    due_date: Optional[datetime] = None
    recurrence_type: RecurrenceType = RecurrenceType.NONE
    recurrence_config: Optional[Dict[str, Any]] = None
    attachments: Optional[List[str]] = []

class TaskCreate(TaskBase):
    user_assignee_ids: Optional[List[UUID]] = []
    role_assignee_ids: Optional[List[UUID]] = []
    steps: Optional[List[TaskStepCreate]] = []
    subtasks: Optional[List[SubTaskCreate]] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_config: Optional[Dict[str, Any]] = None
    user_assignee_ids: Optional[List[UUID]] = None
    role_assignee_ids: Optional[List[UUID]] = None

class TaskStatusUpdate(BaseModel):
    status: TaskStatus

class AssigneeBase(BaseModel):
    id: UUID
    name: str

class UserAssignee(AssigneeBase):
    email: str

class RoleAssignee(AssigneeBase):
    pass

class Task(TaskBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tenant_id: UUID
    created_by: UUID
    subtasks: List[SubTask] = []
    steps: List[TaskStep] = []
    user_assignees: List[UserAssignee] = []
    role_assignees: List[RoleAssignee] = []

# Response models
class TaskResponse(Task):
    pass

class TaskListResponse(BaseModel):
    tasks: List[Task]
    total: int

# Step management
class AddTaskStep(BaseModel):
    order: Optional[int] = None  # If not provided, add at the end
    content_type: ContentType
    content: str

class UpdateTaskStep(BaseModel):
    order: Optional[int] = None
    content_type: Optional[ContentType] = None
    content: Optional[str] = None
    attachments: Optional[List[str]] = None

# Subtask management
class AddSubTask(SubTaskCreate):
    pass

class UpdateSubTask(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    attachments: Optional[List[str]] = None
