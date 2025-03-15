from app.celery_worker.celery_app import celery_app
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.task import Task, TaskStatus, RecurrenceType
from datetime import datetime, timedelta, timezone
import copy
import logging

logger = logging.getLogger(__name__)

@celery_app.task
def process_recurring_tasks():
    """Process all recurring tasks and create new instances if needed."""
    logger.info("Processing recurring tasks")
    db = SessionLocal()
    try:
        # Get all recurring tasks
        recurring_tasks = db.query(Task).filter(
            Task.recurrence_type != RecurrenceType.NONE
        ).all()
        
        now = datetime.now(timezone.utc)
        created_count = 0
        
        for task in recurring_tasks:
            # Skip tasks without due date
            if not task.due_date:
                continue
                
            # Check if we need to create a new task instance
            if should_create_new_instance(task, now):
                create_new_task_instance(db, task, now)
                created_count += 1
        
        logger.info(f"Created {created_count} new recurring task instances")
        db.commit()
        return f"Created {created_count} new recurring task instances"
    except Exception as e:
        logger.error(f"Error processing recurring tasks: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def should_create_new_instance(task, now):
    """Determine if a new task instance should be created based on recurrence settings."""
    # If the task is not completed, don't create a new one
    if task.status != TaskStatus.COMPLETED:
        return False
        
    # If the task was completed and it's past the due date
    if task.completed_at and task.due_date < now:
        if task.recurrence_type == RecurrenceType.DAILY:
            return True
            
        elif task.recurrence_type == RecurrenceType.WEEKLY:
            # Check if we're in a new week
            days_since_completion = (now - task.completed_at).days
            return days_since_completion >= 7
            
        elif task.recurrence_type == RecurrenceType.MONTHLY:
            # Check if we're in a new month
            return (now.month != task.completed_at.month or 
                    now.year != task.completed_at.year)
                    
        elif task.recurrence_type == RecurrenceType.YEARLY:
            # Check if we're in a new year
            return now.year != task.completed_at.year
            
    return False

def create_new_task_instance(db, original_task, now):
    """Create a new instance of a recurring task."""
    # Calculate the new due date
    new_due_date = calculate_next_due_date(original_task, now)
    
    # Create a new task based on the original
    new_task = Task(
        title=original_task.title,
        description=original_task.description,
        status=TaskStatus.NOT_STARTED,
        due_date=new_due_date,
        recurrence_type=original_task.recurrence_type,
        recurrence_config=original_task.recurrence_config,
        tenant_id=original_task.tenant_id,
        created_by=original_task.created_by
    )
    
    # Copy assignees
    new_task.user_assignees = original_task.user_assignees
    new_task.role_assignees = original_task.role_assignees
    
    # Add to database
    db.add(new_task)
    db.flush()
    
    # Copy subtasks
    for subtask in original_task.subtasks:
        new_subtask = copy.copy(subtask)
        new_subtask.id = None
        new_subtask.parent_task_id = new_task.id
        new_subtask.status = TaskStatus.NOT_STARTED
        new_subtask.completed_at = None
        db.add(new_subtask)
    
    # Copy steps
    for step in original_task.steps:
        new_step = copy.copy(step)
        new_step.id = None
        new_step.task_id = new_task.id
        db.add(new_step)
    
    return new_task

def calculate_next_due_date(task, now):
    """Calculate the next due date based on recurrence settings."""
    if not task.due_date:
        return None
        
    if task.recurrence_type == RecurrenceType.DAILY:
        return now + timedelta(days=1)
        
    elif task.recurrence_type == RecurrenceType.WEEKLY:
        return now + timedelta(days=7)
        
    elif task.recurrence_type == RecurrenceType.MONTHLY:
        # Simple approach: same day next month
        next_month = now.month + 1
        next_year = now.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        
        day = min(task.due_date.day, 28)  # Avoid issues with February
        return datetime(next_year, next_month, day, 
                       task.due_date.hour, task.due_date.minute, 
                       tzinfo=timezone.utc)
                       
    elif task.recurrence_type == RecurrenceType.YEARLY:
        return datetime(now.year + 1, task.due_date.month, task.due_date.day,
                       task.due_date.hour, task.due_date.minute,
                       tzinfo=timezone.utc)
                       
    return None 