from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query,Body
from sqlalchemy.orm import Session
from typing import List
import boto3
import asyncio
from datetime import datetime, timedelta
import uuid
from app.models.app import File as FileModel, Tag
from app.schemas.app import FileOut, FileUploadResponse,TagOut
from app.db.session import get_db
from app.core.security import get_current_user
from sqlalchemy import func
from app.models.user import User as DBUser
from app.core.config import FILE_AWS_S3_BUCKET
from datetime import timezone
from rapidfuzz import fuzz  # Make sure to install via `pip install rapidfuzz`


router = APIRouter()

AWS_REGION = "ap-south-1"
AWS_BUCKET = FILE_AWS_S3_BUCKET
s3_client = boto3.client("s3", region_name=AWS_REGION)


# Endpoint for file upload with tags.
@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form(...),
    db: Session = Depends(get_db),
    user: DBUser = Depends(get_current_user)
):

    file_uuid = str(uuid.uuid4())
    s3_key = f"uploads/{file_uuid}_{file.filename}"

    try:
        s3_client.upload_fileobj(file.file, AWS_BUCKET, s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

    tag_names = [t.strip() for t in tags.split(",") if t.strip()]
    db_file = FileModel(file_name=file.filename, s3_key=s3_key)

    for tag_name in tag_names:
        tag_obj = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag_obj:
            tag_obj = Tag(name=tag_name)
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
        tags=[tag.name for tag in db_file.tags]
    )

# Helper function to check restoration status.
def is_restored(head_object: dict) -> bool:
    # The header key is "Restore" – its value might look like:
    # 'ongoing-request="false", expiry-date="Wed, 07 Apr 2021 00:00:00 GMT"'
    restore_status = head_object.get("Restore")
    if restore_status and 'ongoing-request="false"' in restore_status:
        return True
    return False

@router.get("/download/{file_id}")
def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: DBUser = Depends(get_current_user)  # Assume your role-check here
):
    
    db_file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    now = datetime.now(timezone.utc)
    file_age = now - db_file.created_at

    # For files uploaded within 2 days, simply return the presigned URL.
    if file_age < timedelta(days=2):
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": AWS_BUCKET, "Key": db_file.s3_key},
            ExpiresIn=3600  # e.g., 1 hour
        )
        return {"status": "ready", "download_url": url}

    # File is in Glacier. Check its restoration status.
    try:
        head_obj = s3_client.head_object(Bucket=AWS_BUCKET, Key=db_file.s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to head object: {str(e)}")

    # If not yet restored, initiate restore (if not already done) and return pending.
    if not head_obj.get("Restore") or 'ongoing-request="true"' in head_obj.get("Restore"):
        try:
            s3_client.restore_object(
                Bucket=AWS_BUCKET,
                Key=db_file.s3_key,
                RestoreRequest={
                    'Days': 2,  # once restored, available for 2 days
                    'GlacierJobParameters': {'Tier': 'Expedited'}  # or adjust the Tier as needed
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initiate restoration: {str(e)}")
        return {"status": "pending", "message": "File restoration is in progress. Please try again in 1 minute."}

    # If restoration is complete, generate (or use cached) presigned URL valid for 2 days.
    restored_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": AWS_BUCKET, "Key": db_file.s3_key},
        ExpiresIn=172800  # 2 days in seconds
    )
    db_file.restored_url = restored_url
    db_file.restored_url_expiration = datetime.utcnow() + timedelta(days=2)
    db.commit()
    return {"status": "ready", "download_url": restored_url}



@router.put("/files/{file_id}/tags")
def update_file_tags(
    file_id: int,
    tags: list[str] = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: DBUser = Depends(get_current_user)
):
    
    db_file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Remove current tags (many-to-many relationship)
    db_file.tags = []
    # Add new tags
    for tag_name in tags:
        tag_obj = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag_obj:
            tag_obj = Tag(name=tag_name)
            db.add(tag_obj)
            db.commit()
            db.refresh(tag_obj)
        db_file.tags.append(tag_obj)
    
    db.commit()
    return {"message": "Tags updated successfully."}

    
@router.get("/files/all", response_model=List[FileOut])
def get_all_files(
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, description="Max number of items to return"),
    db: Session = Depends(get_db),
    user: DBUser = Depends(get_current_user)
):
    files = db.query(FileModel).offset(offset).limit(limit).all()
    return files


# Endpoint to search files by tags (same as before).
@router.get("/files/search", response_model=List[FileOut])
def search_files(
    tags: List[str] = Query(...),  # /files/search?tags=tag1&tags=tag2...
    require_all: bool = Query(False),
    db: Session = Depends(get_db),
    user: DBUser = Depends(get_current_user)
):
    if not require_all:
        files = (
            db.query(FileModel)
            .join(FileModel.tags)
            .filter(Tag.name.in_(tags))
            .distinct()
            .all()
        )
        return files
    else:
        from sqlalchemy import func
        files = (
            db.query(FileModel)
            .join(FileModel.tags)
            .filter(Tag.name.in_(tags))
            .group_by(FileModel.id)
            .having(func.count(Tag.id) == len(tags))
            .all()
        )
        return files
    

@router.get("/tags/suggestions", response_model=List[TagOut])
def tag_suggestions(
    query: str = Query(..., min_length=1, description="Partial tag name to search for"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, description="Max number of items to return"),
    db: Session = Depends(get_db),
    user: DBUser = Depends(get_current_user)
):
    all_tags = db.query(Tag).all()
    
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