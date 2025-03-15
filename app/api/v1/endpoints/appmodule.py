from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Dict
import asyncio
from datetime import datetime, timedelta
import uuid
import re
from app.models.app import File as FileModel, Tag
from app.schemas.app import FileOut, FileUploadResponse, TagOut, TagInput
from app.db.session import get_db
from app.core.security import get_current_user
from sqlalchemy import func
from app.models.user import User as DBUser
from app.core.config import FILE_AWS_S3_BUCKET
from datetime import timezone
from rapidfuzz import fuzz
from app.utils.s3 import (
    upload_file_with_tags,
    get_download_url,
    delete_object,
    is_restored
)
from app.utils.csv_utils import generate_model_csv

router = APIRouter()

# Constants
AWS_BUCKET = FILE_AWS_S3_BUCKET

# Endpoint for file upload with tags.
@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    try:
        # Upload file to S3 using the utility function
        s3_key = await upload_file_with_tags(file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

    # Parse the new tag format: {type1 : [tag1,tag2] } { type2 : [ tag2,tag2] }
    tag_types = {}
    # Match pattern like {type : [tag1,tag2]}
    pattern = r'\{([^:]+):\s*\[(.*?)\]\s*\}'
    matches = re.findall(pattern, tags)
    
    for tag_type, tag_list in matches:
        # Split by comma and handle potential spaces around tags
        tag_names = [t.strip().strip('"\'') for t in tag_list.split(",") if t.strip()]
        tag_types[tag_type.strip()] = tag_names

    db_file = FileModel(file_name=file.filename, s3_key=s3_key, tenant_id=current_user.tenant_id)

    for tag_type, tag_names in tag_types.items():
        for tag_name in tag_names:
            # Check if tag with same name and type exists
            tag_obj = db.query(Tag).filter(
                Tag.name == tag_name,
                Tag.type == tag_type,
                Tag.tenant_id == current_user.tenant_id
            ).first()
            
            if not tag_obj:
                tag_obj = Tag(
                    name=tag_name,
                    type=tag_type,
                    tenant_id=current_user.tenant_id
                )
                db.add(tag_obj)
                db.commit()
                db.refresh(tag_obj)
            
            db_file.tags.append(tag_obj)

    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return FileUploadResponse(
        id=db_file.id,
        file_name=db_file.file_name,
        s3_key=db_file.s3_key,
        tags=db_file.tags
    )

@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user) 
):
    # Get the file from the database
    db_file = db.query(FileModel).filter(FileModel.id == file_id, FileModel.tenant_id == current_user.tenant_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Calculate file age
    now = datetime.now(timezone.utc)
    file_age = now - db_file.created_at

    try:
        # Use the utility function to get the download URL
        status, result = await get_download_url(AWS_BUCKET, db_file.s3_key, file_age)
        
        if status == "ready":
            # If the file is ready, update the restored URL in the database
            if file_age >= timedelta(days=2):
                db_file.restored_url = result
                db_file.restored_url_expiration = datetime.utcnow() + timedelta(days=2)
                db.commit()
            
            return {"status": "ready", "download_url": result}
        else:
            # If the file is pending restoration
            return {"status": "pending", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/files/{file_id}/tags")
async def update_file_tags(
    file_id: int,
    tag_input: TagInput = Body(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    db_file = db.query(FileModel).filter(FileModel.id == file_id, FileModel.tenant_id == current_user.tenant_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Remove current tags (many-to-many relationship)
    db_file.tags = []
    
    # Add new tags based on type
    for tag_type, tag_names in tag_input.tags.items():
        for tag_name in tag_names:
            # Check if tag with same name and type exists
            tag_obj = db.query(Tag).filter(
                Tag.name == tag_name,
                Tag.type == tag_type,
                Tag.tenant_id == current_user.tenant_id
            ).first()
            
            if not tag_obj:
                tag_obj = Tag(
                    name=tag_name,
                    type=tag_type,
                    tenant_id=current_user.tenant_id
                )
                db.add(tag_obj)
                db.commit()
                db.refresh(tag_obj)
            
            db_file.tags.append(tag_obj)
    
    db.commit()
    return {"message": "Tags updated successfully."}

@router.get("/files/all", response_model=List[FileOut])
async def get_all_files(
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, description="Max number of items to return"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    files = db.query(FileModel).filter(FileModel.tenant_id == current_user.tenant_id).offset(offset).limit(limit).all()
    return files

@router.get("/files/search", response_model=List[FileOut])
async def search_files(
    tags: List[str] = Query(None),
    tag_types: List[str] = Query(None),
    type_tag_pairs: str = Query(None, description="Format: type1:tag1,type2:tag2"),
    require_all: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Base query
    query = db.query(FileModel).filter(FileModel.tenant_id == current_user.tenant_id)
    
    # Handle type-tag pairs if provided
    if type_tag_pairs:
        pairs = [pair.strip() for pair in type_tag_pairs.split(",")]
        type_tag_conditions = []
        
        for pair in pairs:
            if ":" in pair:
                tag_type, tag_name = pair.split(":", 1)
                type_tag_conditions.append(
                    db.query(FileModel.id).join(FileModel.tags).filter(
                        Tag.type == tag_type.strip(),
                        Tag.name == tag_name.strip(),
                        Tag.tenant_id == current_user.tenant_id
                    ).exists().correlate(FileModel)
                )
        
        if type_tag_conditions:
            if require_all:
                # All conditions must be met
                for condition in type_tag_conditions:
                    query = query.filter(condition)
            else:
                # Any condition can be met
                from sqlalchemy import or_
                query = query.filter(or_(*type_tag_conditions))
    
    # Legacy tag search (without types)
    elif tags:
        query = query.join(FileModel.tags)
        if not require_all:
            # Any of the tags
            query = query.filter(Tag.name.in_(tags), Tag.tenant_id == current_user.tenant_id).distinct()
        else:
            # All of the tags
            subquery = (
                db.query(FileModel.id)
                .join(FileModel.tags)
                .filter(Tag.name.in_(tags), Tag.tenant_id == current_user.tenant_id)
                .group_by(FileModel.id)
                .having(func.count(Tag.id) == len(tags))
            )
            query = query.filter(FileModel.id.in_(subquery))
    
    # Filter by tag types only
    elif tag_types:
        query = query.join(FileModel.tags).filter(
            Tag.type.in_(tag_types),
            Tag.tenant_id == current_user.tenant_id
        ).distinct()
    
    return query.all()

@router.get("/tags/suggestions", response_model=List[TagOut])
async def tag_suggestions(
    query: str = Query(..., min_length=1, description="Partial tag name to search for"),
    tag_type: str = Query(None, description="Filter suggestions by tag type"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, description="Max number of items to return"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Base query with tenant filter
    tag_query = db.query(Tag).filter(Tag.tenant_id == current_user.tenant_id)
    
    # Add type filter if provided
    if tag_type:
        tag_query = tag_query.filter(Tag.type == tag_type)
    
    all_tags = tag_query.all()
    
    # Use substring matching for very short queries (less than 3 characters)
    if len(query) < 3:
        matched_tags = [(tag, 100) for tag in all_tags if query.lower() in tag.name.lower()]
    else:
        similarity_threshold = 60  # Adjust this threshold as needed
        matched_tags = [
            (tag, fuzz.ratio(tag.name.lower(), query.lower()))
            for tag in all_tags
        ]
        matched_tags = [(tag, score) for tag, score in matched_tags if score >= similarity_threshold]
    
    # Sort the tags by descending matching score
    matched_tags.sort(key=lambda x: x[1], reverse=True)
    
    # Apply pagination
    paginated_tags = matched_tags[offset:offset + limit]
    
    return [tag for tag, score in paginated_tags]

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Query the file record from the database.
    db_file = db.query(FileModel).filter(FileModel.id == file_id, FileModel.tenant_id == current_user.tenant_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete the file from the S3 bucket using the utility function
    try:
        await delete_object(AWS_BUCKET, db_file.s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file from S3: {str(e)}")
    
    # Delete the file record from the database.
    db.delete(db_file)
    db.commit()
    
    return {"message": "File deleted successfully."}

@router.get("/tags/{tag_type}", response_model=List[TagOut])
async def get_tags_by_type(
    tag_type: str,
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max number of items to return"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get tags filtered by a specific type provided in the path
    """
    tags = db.query(Tag).filter(
        Tag.type == tag_type,
        Tag.tenant_id == current_user.tenant_id
    ).offset(offset).limit(limit).all()
    
    return tags

@router.get("/tag_types", response_model=List[str])
async def get_tag_types(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get all available tag types
    """
    # Use distinct to get unique tag types
    tag_types = db.query(Tag.type).filter(
        Tag.tenant_id == current_user.tenant_id
    ).distinct().all()
    
    # Extract values from result tuples and filter out None values
    return [tag_type[0] for tag_type in tag_types if tag_type[0] is not None]

@router.get("/files/export/csv")
async def export_files_to_csv(
    tag_type: str = Query(None, description="Filter by tag type"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Export files to CSV, optionally filtered by tag type
    """
    # Base query
    query = db.query(FileModel).filter(FileModel.tenant_id == current_user.tenant_id)
    
    # Apply tag type filter if provided
    if tag_type:
        query = query.join(FileModel.tags).filter(Tag.type == tag_type).distinct()
    
    # Get the files
    files = query.all()
    
    # Define headers and field mapping
    headers = ["id", "file_name", "s3_key", "created_at", "tags"]
    field_mapping = {
        "tags": "tags"  # This will be handled specially
    }
    
    # Generate the CSV
    return await generate_model_csv(
        models=files,
        headers=headers,
        field_mapping=field_mapping,
        filename="files_export.csv"
    )