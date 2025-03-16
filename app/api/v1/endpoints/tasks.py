from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any
import json
from datetime import datetime, timezone
import asyncio

from app.db.session import get_db
from app.models.task import Task as DBTask, SubTask as DBSubTask, TaskStep as DBTaskStep
from app.models.task import TaskStatus, RecurrenceType
from app.models.user import User as DBUser
from app.models.tenant import Role as DBRole
from app.schemas.task import (
    Task, TaskCreate, TaskUpdate, TaskStatusUpdate, TaskResponse, TaskListResponse,
    SubTask, SubTaskCreate, AddSubTask, UpdateSubTask,
    TaskStep, AddTaskStep, UpdateTaskStep
)
from app.core.security import get_current_user
from app.utils.s3 import upload_file_to_s3, delete_object
from app.core.config import TASKS_FILE_AWS_S3_BUCKET

router = APIRouter()

# Helper function to delete attachments from S3
async def delete_entity_attachments(entity: Any) -> None:
    """Delete all attachments for an entity from S3."""
    if not hasattr(entity, 'attachments') or not entity.attachments:
        return
    
    # Get attachments
    attachments = entity.attachments.split(",") if entity.attachments else []
    attachments = [a for a in attachments if a]  # Remove empty strings
    
    # Delete each attachment from S3
    for url in attachments:
        try:
            # Extract the S3 key from the URL
            # URL format: https://bucket-name.s3.amazonaws.com/key
            s3_key = url.split(".amazonaws.com/")[1]
            await delete_object(TASKS_FILE_AWS_S3_BUCKET, s3_key)
        except Exception as e:
            # Log the error but continue with the deletion
            print(f"Error deleting attachment from S3: {str(e)}")

# Task CRUD operations
@router.post("/", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Create a new task with optional subtasks and steps."""
    # Create the main task
    db_task = DBTask(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        due_date=task_data.due_date,
        recurrence_type=task_data.recurrence_type,
        recurrence_config=task_data.recurrence_config,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id
    )
    
    # Add user assignees
    if task_data.user_assignee_ids:
        user_assignees = db.query(DBUser).filter(
            DBUser.id.in_(task_data.user_assignee_ids),
            DBUser.tenant_id == current_user.tenant_id
        ).all()
        db_task.user_assignees.extend(user_assignees)
    
    # Add role assignees
    if task_data.role_assignee_ids:
        role_assignees = db.query(DBRole).filter(
            DBRole.id.in_(task_data.role_assignee_ids),
            DBRole.tenant_id == current_user.tenant_id
        ).all()
        db_task.role_assignees.extend(role_assignees)
    
    db.add(db_task)
    db.flush()  # Flush to get the task ID without committing
    
    # Add subtasks if provided
    if task_data.subtasks:
        for subtask_data in task_data.subtasks:
            db_subtask = DBSubTask(
                title=subtask_data.title,
                description=subtask_data.description,
                status=subtask_data.status,
                parent_task_id=db_task.id
            )
            db.add(db_subtask)
    
    # Add steps if provided
    if task_data.steps:
        for step_data in task_data.steps:
            db_step = DBTaskStep(
                task_id=db_task.id,
                order=step_data.order,
                content_type=step_data.content_type,
                content=step_data.content
            )
            db.add(db_step)
    
    db.commit()
    db.refresh(db_task)
    
    return db_task

@router.get("/", response_model=TaskListResponse)
async def get_tasks(
    status: Optional[TaskStatus] = None,
    due_date_from: Optional[datetime] = None,
    due_date_to: Optional[datetime] = None,
    assigned_to_me: bool = False,
    assigned_to_role: Optional[int] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Get a list of tasks with optional filtering."""
    # Base query
    query = db.query(DBTask).filter(DBTask.tenant_id == current_user.tenant_id)
    
    # Apply filters
    if status:
        query = query.filter(DBTask.status == status)
    
    if due_date_from:
        query = query.filter(DBTask.due_date >= due_date_from)
    
    if due_date_to:
        query = query.filter(DBTask.due_date <= due_date_to)
    
    if assigned_to_me:
        query = query.filter(DBTask.user_assignees.any(id=current_user.id))
    
    if assigned_to_role:
        query = query.filter(DBTask.role_assignees.any(id=assigned_to_role))
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination
    tasks = query.order_by(desc(DBTask.created_at)).offset(offset).limit(limit).all()
    
    # Convert attachments from comma-separated string to list for each task
    for task in tasks:
        task.attachments = task.attachments.split(",") if task.attachments else []
        for subtask in task.subtasks:
            subtask.attachments = subtask.attachments.split(",") if subtask.attachments else []
        for step in task.steps:
            step.attachments = step.attachments.split(",") if step.attachments else []
    
    return {"tasks": tasks, "total": total}

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Get a single task by ID."""
    task = db.query(DBTask).filter(
        DBTask.id == task_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Convert attachments from comma-separated string to list
    task.attachments = task.attachments.split(",") if task.attachments else []
    for subtask in task.subtasks:
        subtask.attachments = subtask.attachments.split(",") if subtask.attachments else []
    for step in task.steps:
        step.attachments = step.attachments.split(",") if step.attachments else []
    
    return task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Update a task."""
    # Get the task
    db_task = db.query(DBTask).filter(
        DBTask.id == task_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update basic fields
    update_data = task_data.dict(exclude_unset=True)
    
    # Handle attachments separately if provided
    if "attachments" in update_data:
        # Get existing attachments
        existing_attachments = db_task.attachments.split(",") if db_task.attachments else []
        existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
        
        # Find attachments that are being removed
        new_attachments = update_data["attachments"] if update_data["attachments"] is not None else []
        removed_attachments = [url for url in existing_attachments if url not in new_attachments]
        
        # Delete removed attachments from S3
        for url in removed_attachments:
            try:
                # Extract the S3 key from the URL
                # URL format: https://bucket-name.s3.amazonaws.com/key
                s3_key = url.split(".amazonaws.com/")[1]
                await delete_object(TASKS_FILE_AWS_S3_BUCKET, s3_key)
            except Exception as e:
                # Log the error but continue with the update
                print(f"Error deleting attachment from S3: {str(e)}")
        
        # Convert list to comma-separated string for storage
        if update_data["attachments"] is not None:
            update_data["attachments"] = ",".join(update_data["attachments"])
    
    # Handle assignees separately
    user_assignee_ids = update_data.pop("user_assignee_ids", None)
    role_assignee_ids = update_data.pop("role_assignee_ids", None)
    
    # Update the remaining fields
    for key, value in update_data.items():
        setattr(db_task, key, value)
    
    # Update user assignees if provided
    if user_assignee_ids is not None:
        # Clear existing assignees
        db_task.user_assignees = []
        
        if user_assignee_ids:
            # Add new assignees
            user_assignees = db.query(DBUser).filter(
                DBUser.id.in_(user_assignee_ids),
                DBUser.tenant_id == current_user.tenant_id
            ).all()
            db_task.user_assignees.extend(user_assignees)
    
    # Update role assignees if provided
    if role_assignee_ids is not None:
        # Clear existing assignees
        db_task.role_assignees = []
        
        if role_assignee_ids:
            # Add new assignees
            role_assignees = db.query(DBRole).filter(
                DBRole.id.in_(role_assignee_ids),
                DBRole.tenant_id == current_user.tenant_id
            ).all()
            db_task.role_assignees.extend(role_assignees)
    
    # If status is being updated to completed, set completed_at
    if "status" in update_data and update_data["status"] == TaskStatus.COMPLETED:
        db_task.completed_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(db_task)
    
    # Convert attachments from comma-separated string to list
    db_task.attachments = db_task.attachments.split(",") if db_task.attachments else []
    for subtask in db_task.subtasks:
        subtask.attachments = subtask.attachments.split(",") if subtask.attachments else []
    for step in db_task.steps:
        step.attachments = step.attachments.split(",") if step.attachments else []
    
    return db_task

@router.put("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: int,
    status_update: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Update a task's status."""
    db_task = db.query(DBTask).filter(
        DBTask.id == task_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update status
    db_task.status = status_update.status
    
    # If status is being updated to completed, set completed_at
    if status_update.status == TaskStatus.COMPLETED:
        db_task.completed_at = datetime.now(timezone.utc)
    elif db_task.completed_at and status_update.status != TaskStatus.COMPLETED:
        # If task was completed but now it's not, clear completed_at
        db_task.completed_at = None
    
    db.commit()
    db.refresh(db_task)
    
    return db_task

@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Delete a task."""
    db_task = db.query(DBTask).filter(
        DBTask.id == task_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete attachments from S3 for the task
    await delete_entity_attachments(db_task)
    
    # Delete attachments from S3 for all subtasks
    for subtask in db_task.subtasks:
        await delete_entity_attachments(subtask)
    
    # Delete attachments from S3 for all steps
    for step in db_task.steps:
        await delete_entity_attachments(step)
    
    db.delete(db_task)
    db.commit()
    
    return {"message": "Task deleted successfully"}

# Subtask operations
@router.post("/{task_id}/subtasks", response_model=SubTask)
async def add_subtask(
    task_id: int,
    subtask_data: AddSubTask,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Add a subtask to a task."""
    # Check if task exists and belongs to user's tenant
    task = db.query(DBTask).filter(
        DBTask.id == task_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Create subtask
    db_subtask = DBSubTask(
        title=subtask_data.title,
        description=subtask_data.description,
        status=subtask_data.status,
        parent_task_id=task_id
    )
    
    db.add(db_subtask)
    db.commit()
    db.refresh(db_subtask)
    
    return db_subtask

@router.put("/subtasks/{subtask_id}", response_model=SubTask)
async def update_subtask(
    subtask_id: int,
    subtask_data: UpdateSubTask,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Update a subtask."""
    # Get the subtask with tenant check via parent task
    db_subtask = db.query(DBSubTask).join(DBTask).filter(
        DBSubTask.id == subtask_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    
    # Update fields
    update_data = subtask_data.dict(exclude_unset=True)
    
    # Handle attachments separately if provided
    if "attachments" in update_data:
        # Get existing attachments
        existing_attachments = db_subtask.attachments.split(",") if db_subtask.attachments else []
        existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
        
        # Find attachments that are being removed
        new_attachments = update_data["attachments"] if update_data["attachments"] is not None else []
        removed_attachments = [url for url in existing_attachments if url not in new_attachments]
        
        # Delete removed attachments from S3
        for url in removed_attachments:
            try:
                # Extract the S3 key from the URL
                # URL format: https://bucket-name.s3.amazonaws.com/key
                s3_key = url.split(".amazonaws.com/")[1]
                await delete_object(TASKS_FILE_AWS_S3_BUCKET, s3_key)
            except Exception as e:
                # Log the error but continue with the update
                print(f"Error deleting attachment from S3: {str(e)}")
        
        # Convert list to comma-separated string for storage
        if update_data["attachments"] is not None:
            update_data["attachments"] = ",".join(update_data["attachments"])
    
    for key, value in update_data.items():
        setattr(db_subtask, key, value)
    
    # If status is being set to completed, update completed_at
    if subtask_data.status == TaskStatus.COMPLETED and db_subtask.completed_at is None:
        db_subtask.completed_at = datetime.now(timezone.utc)
    # If status is being changed from completed, clear completed_at
    elif subtask_data.status and subtask_data.status != TaskStatus.COMPLETED:
        db_subtask.completed_at = None
    
    db.commit()
    db.refresh(db_subtask)
    
    # Convert attachments from comma-separated string to list
    db_subtask.attachments = db_subtask.attachments.split(",") if db_subtask.attachments else []
    
    return db_subtask

@router.delete("/subtasks/{subtask_id}", response_model=dict)
async def delete_subtask(
    subtask_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Delete a subtask."""
    # Get the subtask with tenant check via parent task
    db_subtask = db.query(DBSubTask).join(DBTask).filter(
        DBSubTask.id == subtask_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    
    # Delete attachments from S3
    await delete_entity_attachments(db_subtask)
    
    db.delete(db_subtask)
    db.commit()
    
    return {"message": "Subtask deleted successfully"}

# Task attachment operations
@router.post("/{task_id}/attachments", response_model=TaskResponse)
async def add_task_attachments(
    task_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Add attachments to a task."""
    # Check if task exists and belongs to user's tenant
    task = db.query(DBTask).filter(
        DBTask.id == task_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get existing attachments
    existing_attachments = task.attachments.split(",") if task.attachments else []
    existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
    
    # Process each uploaded file
    new_attachment_urls = []
    for file in files:
        url = await upload_file_to_s3(file, f"task_{task_id}", bucket=TASKS_FILE_AWS_S3_BUCKET)
        new_attachment_urls.append(url)
    
    # Append new attachments to existing ones
    all_attachments = existing_attachments + new_attachment_urls
    task.attachments = ",".join(all_attachments)
    
    db.commit()
    db.refresh(task)
    
    # Convert attachments string to list for response
    task_dict = task.__dict__.copy()
    task_dict["attachments"] = task.attachments.split(",") if task.attachments else []
    
    return task

# Subtask attachment operations
@router.post("/subtasks/{subtask_id}/attachments", response_model=SubTask)
async def add_subtask_attachments(
    subtask_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Add attachments to a subtask."""
    # Check if subtask exists and belongs to user's tenant
    subtask = db.query(DBSubTask).join(DBTask).filter(
        DBSubTask.id == subtask_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    
    # Get existing attachments
    existing_attachments = subtask.attachments.split(",") if subtask.attachments else []
    existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
    
    # Process each uploaded file
    new_attachment_urls = []
    for file in files:
        url = await upload_file_to_s3(file, f"subtask_{subtask_id}", bucket=TASKS_FILE_AWS_S3_BUCKET)
        new_attachment_urls.append(url)
    
    # Append new attachments to existing ones
    all_attachments = existing_attachments + new_attachment_urls
    subtask.attachments = ",".join(all_attachments)
    
    db.commit()
    db.refresh(subtask)
    
    # Convert attachments string to list for response
    subtask_dict = subtask.__dict__.copy()
    subtask_dict["attachments"] = subtask.attachments.split(",") if subtask.attachments else []
    
    return subtask

# Step attachment operations
@router.post("/steps/{step_id}/attachments", response_model=TaskStep)
async def add_step_attachments(
    step_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Add attachments to a task step."""
    # Check if step exists and belongs to user's tenant
    step = db.query(DBTaskStep).join(DBTask).filter(
        DBTaskStep.id == step_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not step:
        raise HTTPException(status_code=404, detail="Task step not found")
    
    # Get existing attachments
    existing_attachments = step.attachments.split(",") if step.attachments else []
    existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
    
    # Process each uploaded file
    new_attachment_urls = []
    for file in files:
        url = await upload_file_to_s3(file, f"step_{step_id}", bucket=TASKS_FILE_AWS_S3_BUCKET)
        new_attachment_urls.append(url)
    
    # Append new attachments to existing ones
    all_attachments = existing_attachments + new_attachment_urls
    step.attachments = ",".join(all_attachments)
    
    db.commit()
    db.refresh(step)
    
    # Convert attachments string to list for response
    step_dict = step.__dict__.copy()
    step_dict["attachments"] = step.attachments.split(",") if step.attachments else []
    
    return step

# Delete attachment endpoint
@router.delete("/attachments", response_model=dict)
async def delete_attachment(
    url: str = Query(..., description="The S3 URL of the attachment to delete"),
    entity_type: str = Query(..., description="Type of entity: 'task', 'subtask', or 'step'"),
    entity_id: int = Query(..., description="ID of the entity"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Delete an attachment from an entity and remove it from S3."""
    # Determine the entity based on type
    entity = None
    if entity_type == "task":
        entity = db.query(DBTask).filter(
            DBTask.id == entity_id,
            DBTask.tenant_id == current_user.tenant_id
        ).first()
    elif entity_type == "subtask":
        entity = db.query(DBSubTask).join(DBTask).filter(
            DBSubTask.id == entity_id,
            DBTask.tenant_id == current_user.tenant_id
        ).first()
    elif entity_type == "step":
        entity = db.query(DBTaskStep).join(DBTask).filter(
            DBTaskStep.id == entity_id,
            DBTask.tenant_id == current_user.tenant_id
        ).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid entity type")
    
    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} not found")
    
    # Get existing attachments
    existing_attachments = entity.attachments.split(",") if entity.attachments else []
    existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
    
    # Check if the URL exists in attachments
    if url not in existing_attachments:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Extract the S3 key from the URL
    # URL format: https://bucket-name.s3.amazonaws.com/key
    try:
        s3_key = url.split(".amazonaws.com/")[1]
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid S3 URL format")
    
    # Delete from S3
    try:
        await delete_object(TASKS_FILE_AWS_S3_BUCKET, s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete from S3: {str(e)}")
    
    # Remove from entity's attachments
    existing_attachments.remove(url)
    entity.attachments = ",".join(existing_attachments)
    
    db.commit()
    
    return {"message": "Attachment deleted successfully"}

# Task step operations
@router.post("/{task_id}/steps", response_model=TaskStep)
async def add_task_step(
    task_id: int,
    step_data: AddTaskStep,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Add a step to a task."""
    # Check if task exists and belongs to user's tenant
    task = db.query(DBTask).filter(
        DBTask.id == task_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # If order is not provided, add at the end
    if step_data.order is None:
        max_order = db.query(func.max(DBTaskStep.order)).filter(
            DBTaskStep.task_id == task_id
        ).scalar() or 0
        step_data.order = max_order + 1
    
    # Create step
    db_step = DBTaskStep(
        task_id=task_id,
        order=step_data.order,
        content_type=step_data.content_type,
        content=step_data.content
    )
    
    db.add(db_step)
    db.commit()
    db.refresh(db_step)
    
    return db_step

@router.put("/steps/{step_id}", response_model=TaskStep)
async def update_task_step(
    step_id: int,
    step_data: UpdateTaskStep,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Update a task step."""
    # Get the step with tenant check via parent task
    db_step = db.query(DBTaskStep).join(DBTask).filter(
        DBTaskStep.id == step_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_step:
        raise HTTPException(status_code=404, detail="Task step not found")
    
    # Update fields
    update_data = step_data.dict(exclude_unset=True)
    
    # Handle attachments separately if provided
    if "attachments" in update_data:
        # Get existing attachments
        existing_attachments = db_step.attachments.split(",") if db_step.attachments else []
        existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
        
        # Find attachments that are being removed
        new_attachments = update_data["attachments"] if update_data["attachments"] is not None else []
        removed_attachments = [url for url in existing_attachments if url not in new_attachments]
        
        # Delete removed attachments from S3
        for url in removed_attachments:
            try:
                # Extract the S3 key from the URL
                # URL format: https://bucket-name.s3.amazonaws.com/key
                s3_key = url.split(".amazonaws.com/")[1]
                await delete_object(TASKS_FILE_AWS_S3_BUCKET, s3_key)
            except Exception as e:
                # Log the error but continue with the update
                print(f"Error deleting attachment from S3: {str(e)}")
        
        # Convert list to comma-separated string for storage
        if update_data["attachments"] is not None:
            update_data["attachments"] = ",".join(update_data["attachments"])
    
    for key, value in update_data.items():
        setattr(db_step, key, value)
    
    db.commit()
    db.refresh(db_step)
    
    # Convert attachments from comma-separated string to list
    db_step.attachments = db_step.attachments.split(",") if db_step.attachments else []
    
    return db_step

@router.delete("/steps/{step_id}", response_model=dict)
async def delete_task_step(
    step_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """Delete a task step."""
    # Get the step with tenant check via parent task
    db_step = db.query(DBTaskStep).join(DBTask).filter(
        DBTaskStep.id == step_id,
        DBTask.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_step:
        raise HTTPException(status_code=404, detail="Task step not found")
    
    # Get the task ID and current order for reordering
    task_id = db_step.task_id
    current_order = db_step.order
    
    # Delete attachments from S3
    await delete_entity_attachments(db_step)
    
    # Delete the step
    db.delete(db_step)
    
    # Reorder remaining steps
    remaining_steps = db.query(DBTaskStep).filter(
        DBTaskStep.task_id == task_id,
        DBTaskStep.order > current_order
    ).all()
    
    for step in remaining_steps:
        step.order -= 1
    
    db.commit()
    
    return {"message": "Task step deleted successfully"} 