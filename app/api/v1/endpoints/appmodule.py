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
from fastapi.responses import StreamingResponse
import io
import csv
from rapidfuzz import fuzz

router = APIRouter()
files_repo = FilesRepository()
tags_repo = TagsRepository()

"""
Note: Buckets are now automatically created in the tenant creation process.
"""

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form("{}"),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
    
    # Parse tags from form data
    try:
        tags_data = json.loads(tags)
    except json.JSONDecodeError:
        tags_data = {}
    
    # Upload file to S3
    s3_key = f"{tenant_id}/{str(uuid4())}/{file.filename}"
    s3_url = await upload_file_to_s3(file, s3_key, bucket_name)
    
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
    
    return {
        "id": file_id,
        "file_name": file.filename,
        "s3_key": s3_key,
        "s3_url": s3_url,
        "tags": file_record["tags"]
    }

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
    tag: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    files = await files_repo.files_with_tags(tenant_id=tenant_id, limit=limit, skip=offset)

    
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
    limit: int = Query(default=10, le=100),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    # Use the repository method to get files with tag details
    files = await files_repo.files_by_tag_ids(
        tenant_id=tenant_id, 
        tag_ids=tag_ids,
        skip=offset,
        limit=limit
    )
    
    result = []
    for file in files:
        # Group tags by type
        tags_by_type = {}
        
        # First collect all tags by their type
        for tag in file.get("tag_details", []):
            tag_type = tag.get("type", "default")
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
                
            # Add the tag with id as key, name as value
            tags_by_type[tag_type].append({tag["_id"]: tag["name"]})
        
        # Now format tags as requested
        formatted_tags = []
        for tag_type, tags in tags_by_type.items():
            # Always use array format for all tag types
            formatted_tags.append({tag_type: tags})
        
        result.append({
            "id": file["_id"],
            "file_name": file["file_name"],
            "s3_key": file["s3_key"],
            "created_at": file["created_at"],
            "tags": formatted_tags
        })
    
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
    offset: int = 0,
    limit: int = Query(default=10, le=50),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    find_query = {"tenant_id": tenant_id}

    find_query["name"] = {"$regex": f"{query}", "$options": "i"}
    tags = await tags_repo.find_many(find_query, limit=limit, skip=offset)
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
