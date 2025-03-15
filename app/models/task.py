from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, DateTime, Text, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.session import Base

# Enum for recurrence types
class RecurrenceType(str, enum.Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

# Enum for task status
class TaskStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

# Association table for task assignees (users)
task_user_assignees = Table(
    "task_user_assignees",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True)
)

# Association table for task assignees (roles)
task_role_assignees = Table(
    "task_role_assignees",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True)
)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.NOT_STARTED, nullable=False)
    
    # Due date and recurrence
    due_date = Column(DateTime(timezone=True), nullable=True)
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.NONE, nullable=False)
    recurrence_config = Column(JSON, nullable=True)  # For storing additional recurrence settings
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tenant relationship
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    tenant = relationship("Tenant", backref="tasks")
    
    # Creator relationship
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator = relationship("User", foreign_keys=[created_by], backref="created_tasks")
    
    # Relationships
    subtasks = relationship("SubTask", back_populates="parent_task", cascade="all, delete-orphan")
    steps = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan", order_by="TaskStep.order")
    
    # Assignees
    user_assignees = relationship("User", secondary=task_user_assignees, backref="assigned_tasks")
    role_assignees = relationship("Role", secondary=task_role_assignees, backref="assigned_tasks")

class SubTask(Base):
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.NOT_STARTED, nullable=False)
    
    # Parent task relationship
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    parent_task = relationship("Task", back_populates="subtasks")
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    order = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False)  # "text", "image", "video"
    content = Column(Text, nullable=False)  # Text content or URL to media
    
    # Relationship
    task = relationship("Task", back_populates="steps")
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 