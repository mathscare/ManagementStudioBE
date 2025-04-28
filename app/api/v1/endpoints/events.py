from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query, Response, Form
from typing import List, Optional, Dict, Any
import json
import tempfile
import os
from datetime import datetime, date, timedelta
from uuid import uuid4
from io import BytesIO
from app.db.repository.events import EventsRepository
from app.schemas.event import (
    EventCreate, Event, EventUpdate, EventStatusUpdate,
    EmailTextRequest, AIExtractedField, AIEventExtraction
)
from app.utils.s3 import upload_file_to_s3, delete_object, create_s3_bucket
from app.utils.pdf_generator import generate_event_pdf
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user
from app.utils.csv_utils import generate_model_csv
from pydantic import BaseModel
from app.utils.openai_api import gpt
from app.utils.pdf_utils import convert_pdf_to_images
from dateutil import parser as date_parser


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
    
    event_dict = event_data.dict()
    event_dict["_id"] = str(uuid4())
    event_dict["tenant_id"] = tenant_id
    event_dict["attachments"] = ""
    event_dict["created_at"] = datetime.utcnow()
    event_dict["updated_at"] = datetime.utcnow()
    event_dict["is_active"] = True
    
    if "is_camera_man_hired" not in event_dict:
        event_dict["is_camera_man_hired"] = False
    if "camera_man_number" not in event_dict:
        event_dict["camera_man_number"] = ""
    if "camera_man_name" not in event_dict:
        event_dict["camera_man_name"] = ""
    
    event_dict = prepare_event_for_storage(event_dict)
    
    await events_repo.insert_one(event_dict)
    
    created_event = await events_repo.find_one({"_id": event_dict["_id"]})
    
    created_event["attachments"] = created_event["attachments"].split(",") if created_event["attachments"] else []
    created_event["id"] = created_event.pop("_id") 
    
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
    search: Optional[str] = Query(None, description="Search in event name, institute name, and location"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    tenant_id = current_user["tenant_id"]
    
    # Build base query
    query = {"tenant_id": tenant_id}
    
    # Add search filter if provided
    if search:
        query = {
            "$and": [
                {"tenant_id": tenant_id},
                {"$or": [
                    {"event_name": {"$regex": search, "$options": "i"}},
                    {"institute_name": {"$regex": search, "$options": "i"}},
                    {"location": {"$regex": search, "$options": "i"}}
                ]}
            ]
        }
    
    # Build sort parameters if provided
    sort_params = None
    if sort_field:
        sort_params = [(sort_field, sort_order)]
    
    # Use the updated repository method with pagination and sorting
    events = await events_repo.find_many(
        query,
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

@router.post("/extract-from-email", response_model=AIEventExtraction)
async def extract_event_from_email(
    email_text: str = Form(..., description="Email text to extract event details from"),
    files: Optional[List[UploadFile]] = File(None, description="Optional files (images or PDFs) to include for extraction"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        # Common prompt for both text and image-based extraction
        prompt = """
        You are an AI assistant that extracts event information from emails and attached images or documents.
        Extract the following fields from the provided content:
        - event_name: Name of the event
        - description: Description of the event
        - event_date: Date of the event in YYYY-MM-DD format
        - location: Location where the event will be held
        - institute_name: Name of the institute/organization hosting the event
        - contact_name: Name of the contact person
        - contact_number: Phone number of the contact person
        - email: Email address for contact
        - website: Website of the event or institute (as a valid URL)
        - expected_audience: Expected number of attendees as a number
        - is_paid_event: Whether it's a paid event (true or false)
        - fees: Fee amount if it's a paid event as a number
        - payment_status: Current payment status
        - travel_accomodation: Travel and accommodation details
        - status: Current status of the event planning
        
        For each field, provide the extracted value or null if you can't extract it.
        Respond with a JSON object that follows the specified schema.
        """
        
        image_paths = []
        pdf_files = []
        ai_extraction = None
        
        # Process uploaded files
        if files:
            for file in files:
                if file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_img:
                            temp_img.write(await file.read())
                            image_paths.append(temp_img.name)
                    except Exception as e:
                        print(f"Error saving uploaded image {file.filename}: {str(e)}")
                elif file.filename.lower().endswith('.pdf'):
                    # Rewind the file before adding it to the list
                    await file.seek(0)
                    pdf_files.append(file)
        
        # Process PDF files - convert to images
        if pdf_files:
            try:
                for pdf_file in pdf_files:
                    # Convert PDF to images
                    pdf_images = await convert_pdf_to_images(pdf_file)
                    image_paths.extend(pdf_images)
            except Exception as e:
                print(f"Error processing PDF files: {str(e)}")
        
        # Validate image paths exist before proceeding
        valid_image_paths = [path for path in image_paths if os.path.exists(path)]
        print(f"Valid image paths: {valid_image_paths}")
        # Try to use images if we have valid paths
        if valid_image_paths:
            try:
                enhanced_prompt = f"Email text: {email_text}\n\nAnalyze the email text and any provided images or document scans to extract event details."
                ai_extraction = await gpt.send_images(image_paths=valid_image_paths, prompt=enhanced_prompt,response_model=AIEventExtraction)
                print(f"Image extraction result type: {type(ai_extraction)}")
            except Exception as e:
                print(f"Error with send_images, falling back to text only: {str(e)}")
                # If image processing failed, we'll fall back to text-only
                ai_extraction = None
            
            # Parse string response if needed
            if isinstance(ai_extraction, str):
                try:
                    ai_extraction = json.loads(ai_extraction)
                except Exception as e:
                    print(f"Error parsing image extraction result as JSON: {str(e)}")
        
        # If images failed or weren't provided, use text-only
        if ai_extraction is None:
            text = f"Email text: {email_text}"
            ai_extraction = await gpt.send_text(text=text, prompt=prompt, model=AIEventExtraction)
        
        # Clean up temporary files
        for path in image_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Error removing temp file {path}: {str(e)}")
        
        # Process extraction results
        event_data = {
            "contact_name": None,
            "contact_number": None,
            "description": None,
            "email": None,
            "event_date": None,
            "event_name": None,
            "expected_audience": None,
            "fees": None,
            "institute_name": None,
            "is_paid_event": None,
            "location": None,
            "payment_status": None,
            "travel_accomodation": None,
            "website": None,
            "is_camera_man_hired": None,
            "camera_man_name": None,
            "camera_man_number": None
        }
        
        # Extract fields from the AI response
        if isinstance(ai_extraction, dict):
            for field in event_data:
                if field in ai_extraction and ai_extraction[field] is not None:
                    event_data[field] = ai_extraction[field]
        else:
            for field in event_data:
                if hasattr(ai_extraction, field) and getattr(ai_extraction, field) is not None:
                    event_data[field] = getattr(ai_extraction, field)
        
        # Set default event date if missing to avoid validation errors
        if not event_data["event_date"]:
            event_data["event_date"] = datetime.now().date().isoformat()
        
        try:
            return AIEventExtraction(**event_data)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid event data format: {str(e)}")
            
    except Exception as e:
        # Ensure any temporary files are cleaned up in case of error
        if 'image_paths' in locals() and image_paths:
            for path in image_paths:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
                        
        raise HTTPException(status_code=500, detail=f"Error extracting event information: {str(e)}")

def convert_to_date(date_string: str) -> date:
    """
    Convert a string date to a date object.
    Supports various date formats.
    
    Args:
        date_string: String representing a date
        
    Returns:
        date: A date object
        
    Raises:
        ValueError: If the date string cannot be parsed
    """
    try:
        parsed_date = date_parser.parse(date_string, fuzzy=True)
        return parsed_date.date()
    except Exception:
        formats = [
            "%Y-%m-%d",           
            "%d/%m/%Y",           
            "%m/%d/%Y",           
            "%d-%m-%Y",           
            "%d %B %Y",           # 15 January 2023
            "%d %b %Y",           # 15 Jan 2023
            "%B %d, %Y",          # January 15, 2023
            "%b %d, %Y",          # Jan 15, 2023
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt).date()
            except ValueError:
                continue
        
        # If all parsing attempts fail
        raise ValueError(f"Could not parse date from: {date_string}")

