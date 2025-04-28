from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from typing import List, Dict, Optional
from app.db.repository.files import FilesRepository
from app.db.repository.tags import TagsRepository
from app.schemas.app import FileOut, TagOut, FileUploadResponse, TagInput
from app.core.security import get_current_user
from uuid import uuid4
from datetime import datetime, timedelta
import json
from app.utils.s3 import upload_file_to_s3, delete_object,generate_presigned_url
from app.utils.video_utils import generate_video_thumbnail
from fastapi.responses import StreamingResponse
import io
import csv
from rapidfuzz import fuzz
import asyncio
import tempfile
import os

router = APIRouter()
files_repo = FilesRepository()
tags_repo = TagsRepository()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form("{}"),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
    
        # Check if file is a video and generate thumbnail
    file_content_type = file.content_type or ""
    file_extension = os.path.splitext(file.filename)[1].lower()
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
    video_content_types = ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/webm', 'video/x-flv', 'video/x-ms-wmv']
    
    # Parse tags from form data
    try:
        tags_data = json.loads(tags)
    except json.JSONDecodeError:
        tags_data = {}
        
    # Read file content once
    file_content = await file.read()
    
    # Create a new UploadFile-like object for S3 upload
    file_for_s3 = UploadFile(
        filename=file.filename,
        file=io.BytesIO(file_content),
    )
    
    # Create a new UploadFile-like object for thumbnail generation
    file_for_thumbnail = UploadFile(
        filename=file.filename,
        file=io.BytesIO(file_content),
    )
    
    # Upload file to S3
    s3_key = f"{tenant_id}/{str(uuid4())}/{file.filename}"
    s3_url = await upload_file_to_s3(file_for_s3, s3_key, bucket_name)
    
    # Create file record
    file_id = str(uuid4())
    file_record = {
        "_id": file_id,
        "file_name": file.filename,
        "s3_key": s3_key,
        "s3_url": s3_url,
        "created_at": datetime.now(),
        "tenant_id": tenant_id,
        "tags": []
    }
    

    is_video = (file_content_type.startswith('video/') or 
                file_content_type in video_content_types or 
                file_extension in video_extensions)
    
    if is_video:
                
        thumbnail_result = await generate_video_thumbnail(file_for_thumbnail)
        
        
        if thumbnail_result:
            thumbnail_data, content_type = thumbnail_result
            
            # Upload thumbnail to S3
            thumbnail_key = f"{tenant_id}/{str(uuid4())}/thumbnail_{file.filename}.jpg"
            
            # Create upload file object for the thumbnail
            thumbnail_upload = UploadFile(
                filename=f"thumbnail_{file.filename}.jpg",
                file=io.BytesIO(thumbnail_data),
            )
            
            # Upload to S3
            thumbnail_url = await upload_file_to_s3(thumbnail_upload, thumbnail_key, bucket_name)
            file_record["thumbnail_url"] = thumbnail_url
            print(f"Thumbnail uploaded to S3: {thumbnail_url}","file record",file_record)
    
    # Process tags
    for tag_type, tag_list in tags_data.items():
        for tag_name in tag_list:
            # Check if tag exists
            existing_tag = await tags_repo.find_one({
                "name": tag_name,
                "type": tag_type,
                "tenant_id": tenant_id
            })
            
            if existing_tag:
                tag_id = existing_tag["_id"]
            else:
                # Create new tag
                tag_id = str(uuid4())
                await tags_repo.insert_one({
                    "_id": tag_id,
                    "name": tag_name,
                    "type": tag_type,
                    "tenant_id": tenant_id
                })
            
            # Add tag to file record
            file_record["tags"].append(tag_id)
    
    # Save file record
    await files_repo.insert_one(file_record)
    
    response = {
        "id": file_id,
        "file_name": file.filename,
        "s3_key": s3_key,
        "s3_url": s3_url,
        "tags": file_record["tags"]
    }
    
    # Add thumbnail_url to response if available
    if "thumbnail_url" in file_record:
        response["thumbnail_url"] = file_record["thumbnail_url"]
    
    return response

@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
    
    # Get file record from database
    file = await files_repo.find_one({"_id": file_id, "tenant_id": tenant_id})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    s3_key = file["s3_key"]
    # Remove Glacier checks; directly get download URL
    url = await generate_presigned_url(bucket_name, s3_key)
    
    return {"download_url": url}

@router.get("/files", response_model=List[FileOut])
async def get_files(
    offset: int = 0,
    limit: int = Query(default=10, le=100),
    tag_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    # Call appropriate repository method based on whether tag_type is provided
    if tag_type:
        # Filter files by tag_type
        files = await files_repo.files_with_tags_by_type(
            tenant_id=tenant_id, 
            tag_type=tag_type,
            limit=limit, 
            skip=offset
        )
    else:
        # Get all files without tag type filtering
        files = await files_repo.files_with_tags(
            tenant_id=tenant_id, 
            limit=limit, 
            skip=offset,
            sort={"created_at": -1}  # Sort by created_at descending (newest first)
        )
    
    result = []
    for file in files:
        result.append({
            "id": file["_id"],
            "file_name": file["file_name"],
            "s3_key": file["s3_key"],
            "created_at": file["created_at"],
            "tags": file.get("tags", [])  # Leave as list of tag IDs to match schema
        })
    
    return result

@router.get("/files/by-tags", response_model=List[Dict])  # Changed to Dict as we're modifying the structure
async def get_files_by_tags(
    tag_ids: List[str] = Query(..., description="List of tag IDs to filter by"),
    offset: int = 0,
    limit: int = Query(default=10, le=1000),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    files = await files_repo.files_by_tag_ids(
        tenant_id=tenant_id, 
        tag_ids=tag_ids,
        skip=offset,
        limit=limit
    )
    
    result = []
    for file in files:
        tags_by_type = {}
        
        for tag in file.get("tag_details", []):
            tag_type = tag.get("type", "default")
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
                
            tags_by_type[tag_type].append({tag["_id"]: tag["name"]})
        
        formatted_tags = []
        for tag_type, tags in tags_by_type.items():
            formatted_tags.append({tag_type: tags})
        
        file_data = {
            "id": file["_id"],
            "file_name": file["file_name"],
            "s3_key": file["s3_key"],
            "s3_url": file["s3_url"],
            "created_at": file["created_at"],
            "tags": formatted_tags
        }
        
        # Add thumbnail_url to response if it exists
        if "thumbnail_url" in file:
            file_data["thumbnail_url"] = file["thumbnail_url"]
        
        result.append(file_data)
    
    return result

@router.get("/tags/{tag_type}", response_model=List[TagOut])
async def get_tags_by_type(
    tag_type: str,
    offset: int = 0,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    tags = await tags_repo.find_many(
        {"type": tag_type, "tenant_id": tenant_id}, 
        limit=limit, 
        skip=offset
    )
    return [
        {
            "id": tag["_id"],
            "name": tag["name"],
            "type": tag.get("type", "default")
        } for tag in tags
    ]


@router.get("/tags-suggestions", response_model=List[TagOut])
async def tag_suggestions(
    query: str = Query(...),
    tag_ids: Optional[List[str]] = Query(None, description="List of tag IDs to filter by"),
    offset: int = 0,
    limit: int = Query(default=10, le=50),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    # Use the new repository method with a single pipeline
    tags = await tags_repo.get_tag_suggestions(
        tenant_id=tenant_id,
        query=query,
        tag_ids=tag_ids,
        skip=offset,
        limit=limit
    )
    
    return [
        {
            "id": tag["_id"],
            "name": tag["name"],
            "type": tag.get("type", "default")
        } for tag in tags
    ]

@router.put("/files/{file_id}/tags", response_model=FileOut)
async def update_file_tags(
    file_id: str,
    tag_input: TagInput,
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    # Find the file
    file = await files_repo.find_one({"_id": file_id, "tenant_id": tenant_id})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Process new tags
    new_tag_ids = []
    for tag_type, tag_names in tag_input.tags.items():
        for tag_name in tag_names:
            # Check if tag exists
            existing_tag = await tags_repo.find_one({
                "name": tag_name,
                "type": tag_type,
                "tenant_id": tenant_id
            })
            
            if existing_tag:
                tag_id = existing_tag["_id"]
            else:
                # Create new tag
                tag_id = str(uuid4())
                await tags_repo.insert_one({
                    "_id": tag_id,
                    "name": tag_name,
                    "type": tag_type,
                    "tenant_id": tenant_id
                })
            
            new_tag_ids.append(tag_id)
    
    # Update file with new tags
    await files_repo.update_one({"_id": file_id}, {"tags": new_tag_ids})
    
    # Return updated file with only tag IDs to match the FileOut schema
    updated_file = await files_repo.files_with_tags(tenant_id=tenant_id, limit=1, skip=0, id=file_id)
    
    return {
        "id": updated_file["_id"],
        "file_name": updated_file["file_name"],
        "s3_key": updated_file["s3_key"],
        "created_at": updated_file["created_at"],
        "tags": updated_file.get("tags", [])  # Return tag IDs only
    }

@router.delete("/files/{file_id}")
async def delete_file(file_id: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    file = await files_repo.find_one({"_id": file_id, "tenant_id": tenant_id})
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete file from S3
    try:
        await delete_object(file["s3_key"])
    except Exception as e:
        # Log error but continue with deletion from database
        print(f"Error deleting file from S3: {str(e)}")
    
    # Delete file record
    await files_repo.delete_one({"_id": file_id})
    return {"detail": "File deleted successfully"}


