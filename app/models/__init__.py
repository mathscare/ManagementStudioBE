# Import models in the correct order to avoid circular dependencies
from app.models.tenant import Tenant, Role, Permission
from app.models.user import User
from app.models.app import File, Tag
from app.models.event import Event
from app.models.task import Task, TaskStep, Subtask, TaskStatus, RecurrenceType

# This ensures that all models are properly loaded and relationships are established
# before SQLAlchemy tries to create the tables
