from pydantic import BaseModel, Field, HttpUrl, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

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

class TaskStepCreate(TaskStepBase):
    pass

class TaskStep(TaskStepBase):
    id: int
    task_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class SubTaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.NOT_STARTED

class SubTaskCreate(SubTaskBase):
    pass

class SubTask(SubTaskBase):
    id: int
    parent_task_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    due_date: Optional[datetime] = None
    recurrence_type: RecurrenceType = RecurrenceType.NONE
    recurrence_config: Optional[Dict[str, Any]] = None

class TaskCreate(TaskBase):
    user_assignee_ids: Optional[List[int]] = []
    role_assignee_ids: Optional[List[int]] = []
    steps: Optional[List[TaskStepCreate]] = []
    subtasks: Optional[List[SubTaskCreate]] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_config: Optional[Dict[str, Any]] = None
    user_assignee_ids: Optional[List[int]] = None
    role_assignee_ids: Optional[List[int]] = None

class TaskStatusUpdate(BaseModel):
    status: TaskStatus

class AssigneeBase(BaseModel):
    id: int
    name: str

class UserAssignee(AssigneeBase):
    email: str

class RoleAssignee(AssigneeBase):
    pass

class Task(TaskBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tenant_id: int
    created_by: int
    subtasks: List[SubTask] = []
    steps: List[TaskStep] = []
    user_assignees: List[UserAssignee] = []
    role_assignees: List[RoleAssignee] = []

    class Config:
        orm_mode = True

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

# Subtask management
class AddSubTask(SubTaskCreate):
    pass

class UpdateSubTask(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None 