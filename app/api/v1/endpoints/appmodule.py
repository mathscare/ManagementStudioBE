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
                # Update tag with new file reference
                files = existing_tag.get("files", [])
                if file_id not in files:
                    files.append(file_id)
                await tags_repo.update_one(
                    {"_id": tag_id},
                    {"files": files}
                )
            else:
                # Create new tag
                tag_id = str(uuid4())
                await tags_repo.insert_one({
                    "_id": tag_id,
                    "name": tag_name,
                    "type": tag_type,
                    "tenant_id": tenant_id,
                    "files": [file_id]
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

@router.get("/files/search", response_model=List[FileOut])
async def search_files(
    query: str = None,
    tag_types: List[str] = Query(None),
    tag_names: List[str] = Query(None),
    type_tag_pairs: str = Query(None),
    require_all: bool = False,
    offset: int = 0,
    limit: int = Query(default=10, le=100),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    # Handle type-tag pairs if provided
    if type_tag_pairs:
        pairs = [pair.strip() for pair in type_tag_pairs.split(",")]
        type_tag_conditions = []
        
        for pair in pairs:
            if ":" in pair:
                tag_type, tag_name = pair.split(":", 1)
                # Find tags matching the criteria
                tags = await tags_repo.find_many({
                    "type": tag_type.strip(),
                    "name": tag_name.strip(),
                    "tenant_id": tenant_id
                })
                
                if tags:
                    # Get file IDs from these tags
                    file_ids = []
                    for tag in tags:
                        file_ids.extend(tag.get("files", []))
                    
                    if file_ids:
                        type_tag_conditions.append({"_id": {"$in": file_ids}})
        
        if type_tag_conditions:
            if require_all:
                # All conditions must be met (intersection of file sets)
                pipeline = [
                    {"$match": {"tenant_id": tenant_id}},
                    {"$match": {"$and": type_tag_conditions}},
                    {"$skip": offset},
                    {"$limit": limit}
                ]
            else:
                # Any condition can be met (union of file sets)
                pipeline = [
                    {"$match": {"tenant_id": tenant_id}},
                    {"$match": {"$or": type_tag_conditions}},
                    {"$skip": offset},
                    {"$limit": limit}
                ]
                
            files = await files_repo.aggregate(pipeline)
            
            # Format the response with tag IDs only to match the FileOut schema
            result = []
            for file in files:
                result.append({
                    "id": file["_id"],
                    "file_name": file["file_name"],
                    "s3_key": file["s3_key"],
                    "created_at": file["created_at"],
                    "tags": file.get("tags", [])  # Leave as list of tag IDs
                })
            
            return result
    
    # Standard query
    search_query = {"tenant_id": tenant_id}
    
    # Add filename search if query is provided
    if query:
        search_query["file_name"] = {"$regex": query, "$options": "i"}
    
    # Filter by tag types
    if tag_types:
        # Find all tags of the given types
        tags = await tags_repo.find_many({
            "type": {"$in": tag_types},
            "tenant_id": tenant_id
        })
        
        if tags:
            # Get all file IDs from these tags
            file_ids = []
            for tag in tags:
                file_ids.extend(tag.get("files", []))
            
            if file_ids:
                search_query["_id"] = {"$in": file_ids}
    
    # Filter by tag names
    if tag_names:
        # Find all tags with the given names
        tags = await tags_repo.find_many({
            "name": {"$in": tag_names},
            "tenant_id": tenant_id
        })
        
        if tags:
            # Get all file IDs from these tags
            file_ids = []
            for tag in tags:
                file_ids.extend(tag.get("files", []))
            
            if file_ids:
                if "_id" in search_query:
                    # Intersect with existing file IDs
                    existing_ids = search_query["_id"]["$in"]
                    file_ids = [id for id in file_ids if id in existing_ids]
                    search_query["_id"] = {"$in": file_ids}
                else:
                    search_query["_id"] = {"$in": file_ids}
    
    # Get files matching the criteria
    files = await files_repo.find_many(search_query, limit=limit, skip=offset)
    
    result = []
    for file in files:
        result.append({
            "id": file["_id"],
            "file_name": file["file_name"],
            "s3_key": file["s3_key"],
            "created_at": file["created_at"],
            "tags": file.get("tags", [])  # Return tag IDs only
        })
    
    return result

@router.get("/tags", response_model=List[TagOut])
async def get_tags(
    offset: int = 0,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    tags = await tags_repo.find_many({"tenant_id": tenant_id}, limit=limit, skip=offset)
    return [
        {
            "id": tag["_id"],
            "name": tag["name"],
            "type": tag.get("type", "default")
        } for tag in tags
    ]

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

@router.get("/tag_types", response_model=List[str])
async def get_tag_types(
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {"_id": "$type"}},
        {"$project": {"type": "$_id", "_id": 0}}
    ]
    
    result = await tags_repo.aggregate(pipeline)
    return [item.get("type") for item in result if item.get("type")]

@router.get("/tags/suggestions", response_model=List[TagOut])
async def tag_suggestions(
    query: str = Query(..., min_length=1),
    tag_type: str = None,
    offset: int = 0,
    limit: int = Query(default=10, le=50),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    
    # Base query
    find_query = {"tenant_id": tenant_id}
    
    # Add type filter if provided
    if tag_type:
        find_query["type"] = tag_type
    
    # For short queries, use regex
    if len(query) < 3:
        find_query["name"] = {"$regex": f".*{query}.*", "$options": "i"}
        tags = await tags_repo.find_many(find_query, limit=limit, skip=offset)
        return [
            {
                "id": tag["_id"],
                "name": tag["name"],
                "type": tag.get("type", "default")
            } for tag in tags
        ]
    
    # For longer queries, do fuzzy matching
    all_tags = await tags_repo.find_many(find_query)
    
    # Calculate fuzzy matches
    fuzzy_matches = []
    for tag in all_tags:
        score = fuzz.ratio(tag["name"].lower(), query.lower())
        if score >= 60:  # Threshold for relevance
            fuzzy_matches.append((tag, score))
    
    # Sort by score, highest first
    fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
    
    # Paginate results
    paginated_matches = fuzzy_matches[offset:offset + limit]
    
    return [
        {
            "id": tag["_id"],
            "name": tag["name"],
            "type": tag.get("type", "default")
        } for tag, score in paginated_matches
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
    
    # Get current tag IDs
    current_tag_ids = file.get("tags", [])
    
    # Remove file reference from current tags
    for tag_id in current_tag_ids:
        tag = await tags_repo.find_one({"_id": tag_id})
        if tag and "files" in tag:
            files = tag["files"]
            if file_id in files:
                files.remove(file_id)
                await tags_repo.update_one({"_id": tag_id}, {"files": files})
    
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
                # Add file reference to tag
                files = existing_tag.get("files", [])
                if file_id not in files:
                    files.append(file_id)
                    await tags_repo.update_one({"_id": tag_id}, {"files": files})
            else:
                # Create new tag
                tag_id = str(uuid4())
                await tags_repo.insert_one({
                    "_id": tag_id,
                    "name": tag_name,
                    "type": tag_type,
                    "tenant_id": tenant_id,
                    "files": [file_id]
                })
            
            new_tag_ids.append(tag_id)
    
    # Update file with new tags
    await files_repo.update_one({"_id": file_id}, {"tags": new_tag_ids})
    
    # Return updated file with only tag IDs to match the FileOut schema
    updated_file = await files_repo.files_with_tags(tenant_id=tenant_id, limit=1, skip=0,id=file_id)
    
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
    
    # Remove file from all tags
    for tag_id in file.get("tags", []):
        tag = await tags_repo.find_one({"_id": tag_id})
        if tag and "files" in tag and file_id in tag["files"]:
            updated_files = [f for f in tag["files"] if f != file_id]
            await tags_repo.update_one({"_id": tag_id}, {"files": updated_files})
    
    # Delete file from S3
    try:
        await delete_object(file["s3_key"])
    except Exception as e:
        # Log error but continue with deletion from database
        print(f"Error deleting file from S3: {str(e)}")
    
    # Delete file record
    await files_repo.delete_one({"_id": file_id})
    return {"detail": "File deleted successfully"}

@router.get("/files/export/csv")
async def export_files_to_csv(
    tag_type: str = None,
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    query = {"tenant_id": tenant_id}
    
    # Add tag type filter if provided
    if tag_type:
        # Find all tags of the specified type
        tags = await tags_repo.find_many({"type": tag_type, "tenant_id": tenant_id})
        if tags:
            # Get all file IDs from these tags
            file_ids = []
            for tag in tags:
                file_ids.extend(tag.get("files", []))
            
            # Only get files that are in this list
            if file_ids:
                query["_id"] = {"$in": file_ids}
            else:
                # No files match this tag type
                query["_id"] = {"$in": []}
    
    # Get files from database
    files = await files_repo.find_many(query)
    
    # Create in-memory CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(["ID", "Filename", "S3 Key", "Created At", "Tags"])
    
    # Write data rows
    for file in files:
        # Get tag names for this file
        tag_names = []
        for tag_id in file.get("tags", []):
            tag = await tags_repo.find_one({"_id": tag_id})
            if tag:
                tag_names.append(f"{tag.get('type', 'default')}:{tag.get('name', '')}")
        
        # Write the row
        writer.writerow([
            file.get("_id", ""),
            file.get("file_name", ""),
            file.get("s3_key", ""),
            file.get("created_at", ""),
            ", ".join(tag_names)
        ])
    
    # Return CSV as streaming response
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=files_export_{datetime.now().strftime('%Y%m%d')}.csv"}
    )