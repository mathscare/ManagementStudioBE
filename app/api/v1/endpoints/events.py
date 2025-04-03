from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query
from typing import List, Optional, Dict, Any
import json
from datetime import datetime, date
from uuid import uuid4
from io import BytesIO

from app.db.repository.events import EventsRepository
from app.schemas.event import EventCreate, Event, EventUpdate, EventStatusUpdate
from app.utils.s3 import upload_file_to_s3, delete_object, create_s3_bucket
from app.utils.pdf_generator import generate_event_pdf
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user
from app.utils.csv_utils import generate_model_csv


router = APIRouter()
events_repo = EventsRepository()

# Helper function to convert fields for MongoDB storage
def prepare_event_for_storage(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert types that MongoDB can't handle natively."""
    result = dict(event_dict)
    
    # Convert date to datetime
    if "event_date" in result and isinstance(result["event_date"], date):
        result["event_date"] = datetime.combine(result["event_date"], datetime.min.time())
    
    # Convert HttpUrl to string
    if "website" in result and result["website"] is not None:
        result["website"] = str(result["website"])
    
    return result

@router.post("/", response_model=Event)
async def create_event(
    event_data: EventCreate = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Create event with additional fields
    event_dict = event_data.dict()
    event_dict["_id"] = str(uuid4())
    event_dict["tenant_id"] = tenant_id
    event_dict["attachments"] = ""
    event_dict["created_at"] = datetime.utcnow()
    event_dict["updated_at"] = datetime.utcnow()
    event_dict["is_active"] = True
    
    # Set default values for camera man fields if not provided
    if "is_camera_man_hired" not in event_dict:
        event_dict["is_camera_man_hired"] = False
    if "camera_man_number" not in event_dict:
        event_dict["camera_man_number"] = ""
    if "camera_man_name" not in event_dict:
        event_dict["camera_man_name"] = ""
    
    # Prepare for MongoDB storage
    event_dict = prepare_event_for_storage(event_dict)
    
    # Insert into database
    await events_repo.insert_one(event_dict)
    
    # Get the created event
    created_event = await events_repo.find_one({"_id": event_dict["_id"]})
    
    # Convert for response
    created_event["attachments"] = created_event["attachments"].split(",") if created_event["attachments"] else []
    created_event["id"] = created_event.pop("_id")  # Replace _id with id for response
    
    return Event(**created_event)

@router.post("/{event_id}/attachments", response_model=Event)
async def add_event_attachments(
    event_id: str,
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Find the event
    event = await events_repo.find_one({"_id": event_id, "tenant_id": tenant_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get existing attachments
    existing_attachments = event["attachments"].split(",") if event["attachments"] else []
    existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
    
    # Define bucket name based on tenant
    bucket_name = f"AWS_S3_BUCKET_{tenant_id}"    
    # Upload new files
    new_attachment_urls = []
    for file in files:
        key = f"{uuid4()}.{file.filename}"
        url = await upload_file_to_s3(file,key,bucket=bucket_name)
        new_attachment_urls.append(url)
    
    # Combine attachments and update
    all_attachments = existing_attachments + new_attachment_urls
    updated_attachments = ",".join(all_attachments)
    
    # Update event with new attachments and updated_at timestamp
    await events_repo.update_one(
        {"_id": event_id}, 
        {
            "attachments": updated_attachments,
            "updated_at": datetime.utcnow()
        }
    )
    
    # Get updated event
    updated_event = await events_repo.find_one({"_id": event_id})
    
    # Format for response
    updated_event["attachments"] = updated_event["attachments"].split(",") if updated_event["attachments"] else []
    updated_event["id"] = updated_event.pop("_id")
    
    return Event(**updated_event)


@router.get("/", response_model=List[Event])
async def get_events(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    sort_field: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: Optional[int] = Query(1, description="Sort order: 1 for ascending, -1 for descending"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Build sort parameters if provided
    sort_params = None
    if sort_field:
        sort_params = [(sort_field, sort_order)]
    
    # Use the updated repository method with pagination and sorting
    events = await events_repo.find_many(
        {"tenant_id": tenant_id},
        skip=offset,
        limit=limit,
        sort=sort_params
    )
    
    # Format for response
    formatted_events = []
    for event in events:
        event_dict = dict(event)
        event_dict["attachments"] = event_dict["attachments"].split(",") if event_dict["attachments"] else []
        event_dict["id"] = event_dict.pop("_id")
        formatted_events.append(Event(**event_dict))
    
    return formatted_events

@router.get("/{event_id}", response_model=Event)
async def get_single_event(
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Find event
    event = await events_repo.find_one({"_id": event_id, "tenant_id": tenant_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Format for response
    event_dict = dict(event)
    event_dict["attachments"] = event_dict["attachments"].split(",") if event_dict["attachments"] else []
    event_dict["id"] = event_dict.pop("_id")
    
    return Event(**event_dict)

@router.put("/{event_id}/form", response_model=Event)
async def update_event_form(
    event_id: str,
    event: EventUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Find event
    existing_event = await events_repo.find_one({"_id": event_id, "tenant_id": tenant_id})
    if not existing_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Prepare update dict
    update_dict = event.dict(exclude_unset=True)
    
    # Handle attachments specially
    if "attachments" in update_dict:
        # Get existing attachments
        existing_attachments = existing_event["attachments"].split(",") if existing_event["attachments"] else []
        existing_attachments = [a for a in existing_attachments if a]
        
        # Find attachments to remove
        new_attachments = update_dict["attachments"]
        removed_attachments = [url for url in existing_attachments if url not in new_attachments]
        
        # Delete from S3
        bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
        for url in removed_attachments:
            try:
                s3_key = url.split(".amazonaws.com/")[1]
                await delete_object(bucket_name, s3_key)
            except Exception as e:
                print(f"Error deleting attachment from S3: {str(e)}")
        
        # Update attachments as comma-separated string
        update_dict["attachments"] = ",".join(new_attachments)
    
    # Add updated_at timestamp
    update_dict["updated_at"] = datetime.utcnow()
    
    # Prepare for MongoDB storage
    update_dict = prepare_event_for_storage(update_dict)
    
    # Update the event
    await events_repo.update_one({"_id": event_id}, update_dict)
    
    # Get updated event
    updated_event = await events_repo.find_one({"_id": event_id})
    
    # Format for response
    updated_event_dict = dict(updated_event)
    updated_event_dict["attachments"] = updated_event_dict["attachments"].split(",") if updated_event_dict["attachments"] else []
    updated_event_dict["id"] = updated_event_dict.pop("_id")
    
    return Event(**updated_event_dict)

@router.put("/{event_id}/status", response_model=Event)
async def update_event_status(
    event_id: str,
    status_update: EventStatusUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Find event
    event = await events_repo.find_one({"_id": event_id, "tenant_id": tenant_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Update status and updated_at timestamp
    update_data = {
        "status": status_update.status,
        "updated_at": datetime.utcnow()
    }
    await events_repo.update_one({"_id": event_id}, update_data)
    
    # Get updated event
    updated_event = await events_repo.find_one({"_id": event_id})
    
    # Format for response
    updated_event_dict = dict(updated_event)
    updated_event_dict["attachments"] = updated_event_dict["attachments"].split(",") if updated_event_dict["attachments"] else []
    updated_event_dict["id"] = updated_event_dict.pop("_id")
    
    return Event(**updated_event_dict)

@router.get("/events/{event_id}/pdf", response_class=StreamingResponse)
async def get_event_pdf(
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Find event
    event = await events_repo.find_one({"_id": event_id, "tenant_id": tenant_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Process attachments for PDF generation
    event_dict = dict(event)
    event_dict["attachments"] = event_dict["attachments"].split(",") if event_dict["attachments"] else []
    
    # Create output buffer
    output_buffer = BytesIO()
    
    # Generate PDF
    generate_event_pdf(event_dict, event_dict["attachments"], output_buffer)
    
    # Reset buffer position
    output_buffer.seek(0)
    
    return StreamingResponse(
        output_buffer, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=event_{event_id}.pdf"}
    )

@router.get("/events/csv")
async def get_events_csv(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Use the updated repository method with pagination
    events = await events_repo.find_many(
        {"tenant_id": tenant_id},
        skip=offset,
        limit=limit
    )
    
    # Define CSV headers
    headers = [
        "id", "contact_name", "contact_number", "description", "email",
        "event_date", "event_name", "expected_audience", "fees", "institute_name",
        "is_paid_event", "location", "payment_status", "travel_accomodation",
        "website", "attachments", "status", "created_at", "updated_at", "is_active",
        "is_camera_man_hired", "camera_man_name", "camera_man_number"
    ]
    
    # Special field handling
    field_mapping = {
        "attachments": "attachments",  # This will be handled specially
        "id": "_id"  # Map MongoDB _id to id for CSV
    }
    
    # Format events for CSV - no need for pagination as it's already done in the repo
    formatted_events = []
    for event in events:
        event_dict = dict(event)
        formatted_events.append(event_dict)
    
    # Generate CSV
    return await generate_model_csv(
        models=formatted_events,
        headers=headers,
        field_mapping=field_mapping,
        filename="events.csv"
    )

# Helper function to delete attachments from S3
async def delete_entity_attachments(entity: Dict[str, Any], tenant_id: str) -> None:
    """Delete all attachments for an entity from S3."""
    if not entity.get("attachments"):
        return
    
    # Get attachments
    attachments = entity["attachments"].split(",") if entity["attachments"] else []
    attachments = [a for a in attachments if a]  # Remove empty strings
    
    # Get bucket name for the tenant
    bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
    
    # Delete each attachment from S3
    for url in attachments:
        try:
            # Extract the S3 key from the URL
            s3_key = url.split(".amazonaws.com/")[1]
            await delete_object(bucket_name, s3_key)
        except Exception as e:
            # Log the error but continue with the deletion
            print(f"Error deleting attachment from S3: {str(e)}")

@router.delete("/{event_id}", response_model=dict)
async def delete_event(
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Find event
    event = await events_repo.find_one({"_id": event_id, "tenant_id": tenant_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Delete attachments from S3
    await delete_entity_attachments(event, tenant_id)
    
    # Delete the event
    await events_repo.delete_one({"_id": event_id})
    
    return {"message": "Event deleted successfully"}

@router.delete("/{event_id}/attachments", response_model=Event)
async def delete_event_attachments(
    event_id: str,
    attachment_urls: str = Query(..., description="Comma-separated list of attachment URLs to delete"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete specific attachments from an event. Requires a comma-separated list of attachment URLs.
    """
    tenant_id = current_user["tenant_id"]
    
    # Find the event
    event = await events_repo.find_one({"_id": event_id, "tenant_id": tenant_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get existing attachments
    existing_attachments = event["attachments"].split(",") if event["attachments"] else []
    existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
    
    # Parse attachment_urls to get URLs to delete
    urls_to_delete = [url.strip() for url in attachment_urls.split(",") if url.strip()]
    
    # Validate that all URLs to delete exist in the event
    invalid_urls = [url for url in urls_to_delete if url not in existing_attachments]
    if invalid_urls:
        raise HTTPException(
            status_code=400, 
            detail=f"The following attachment URLs were not found in the event: {', '.join(invalid_urls)}"
        )
    
    # Delete attachments from S3
    bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
    for url in urls_to_delete:
        try:
            # Extract the S3 key from the URL
            s3_key = url.split(".amazonaws.com/")[1]
            await delete_object(bucket_name, s3_key)
        except Exception as e:
            print(f"Error deleting attachment from S3: {str(e)}")
    
    # Update the event's attachments list
    remaining_attachments = [url for url in existing_attachments if url not in urls_to_delete]
    updated_attachments = ",".join(remaining_attachments)
    
    # Update the event record
    await events_repo.update_one(
        {"_id": event_id}, 
        {
            "attachments": updated_attachments,
            "updated_at": datetime.utcnow()
        }
    )
    
    # Get the updated event
    updated_event = await events_repo.find_one({"_id": event_id})
    
    # Format for response
    updated_event["attachments"] = updated_event["attachments"].split(",") if updated_event["attachments"] else []
    updated_event["id"] = updated_event.pop("_id")
    
    return Event(**updated_event)