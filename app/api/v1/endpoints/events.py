from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
from app.db.session import get_db
from app.models.event import Event as DBEvent
from app.schemas.event import EventCreate, Event, EventUpdate, EventStatusUpdate
from app.utils.s3 import upload_file_to_s3, delete_object
from app.utils.pdf_generator import generate_event_pdf
from fastapi.responses import StreamingResponse
from io import BytesIO
from app.core.security import get_current_user
from app.models.user import User as DBUser
from app.utils.csv_utils import generate_model_csv
from app.core.config import AWS_S3_BUCKET

router = APIRouter()

@router.post("/", response_model=Event)
async def create_event(
    event_data: EventCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    db_event = DBEvent(
        contact_name=event_data.contact_name,
        contact_number=event_data.contact_number,
        description=event_data.description,
        email=event_data.email,
        event_date=event_data.event_date,
        event_name=event_data.event_name,
        expected_audience=event_data.expected_audience,
        fees=event_data.fees,
        institute_name=event_data.institute_name,
        is_paid_event=event_data.is_paid_event,
        location=event_data.location,
        payment_status=event_data.payment_status,
        travel_accomodation=event_data.travel_accomodation,
        website=str(event_data.website) if event_data.website else None,
        attachments="",
        status=event_data.status,
        tenant_id=current_user.tenant_id  
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    db_event.attachments = db_event.attachments.split(",") if db_event.attachments else []
    return db_event

@router.post("/{event_id}/attachments", response_model=Event)
async def add_event_attachments(
    event_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Fetch the event record; if not found, return 404
    db_event = db.query(DBEvent).filter(
        DBEvent.id == event_id,
        DBEvent.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get any existing attachments (assumed stored as a comma-separated string)
    existing_attachments = db_event.attachments.split(",") if db_event.attachments else []
    
    # Process each uploaded file: upload and collect URLs
    new_attachment_urls = []
    for file in files:
        url = await upload_file_to_s3(file, db_event.event_name)
        new_attachment_urls.append(url)
    
    # Append new attachments to existing ones
    all_attachments = existing_attachments + new_attachment_urls
    db_event.attachments = ",".join(all_attachments)
    
    db.commit()
    db.refresh(db_event)
    
    # Return the event with attachments as a list
    db_event.attachments = db_event.attachments.split(",") if db_event.attachments else []
    return db_event

@router.get("/", response_model=List[Event])
async def get_events(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    events = db.query(DBEvent).filter(DBEvent.tenant_id == current_user.tenant_id).offset(offset).limit(limit).all()
    for event in events:
        event.attachments = event.attachments.split(",") if event.attachments else []
    return events

@router.get("/{event_id}", response_model=Event)
async def get_single_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    event = db.query(DBEvent).filter(
        DBEvent.id == event_id,
        DBEvent.tenant_id == current_user.tenant_id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.attachments = event.attachments.split(",") if event.attachments else []
    return event

@router.put("/{event_id}/form", response_model=Event)
async def update_event_form(
    event_id: int,
    event: EventUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    db_event = db.query(DBEvent).filter(
        DBEvent.id == event_id,
        DBEvent.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check if attachments are being updated
    if event.attachments is not None:
        # Get existing attachments
        existing_attachments = db_event.attachments.split(",") if db_event.attachments else []
        existing_attachments = [a for a in existing_attachments if a]  # Remove empty strings
        
        # Find attachments that are being removed
        new_attachments = event.attachments
        removed_attachments = [url for url in existing_attachments if url not in new_attachments]
        
        # Delete removed attachments from S3
        for url in removed_attachments:
            try:
                # Extract the S3 key from the URL
                # URL format: https://bucket-name.s3.amazonaws.com/key
                s3_key = url.split(".amazonaws.com/")[1]
                await delete_object(AWS_S3_BUCKET, s3_key)
            except Exception as e:
                # Log the error but continue with the update
                print(f"Error deleting attachment from S3: {str(e)}")
        
        # Update the attachments field with comma-separated string
        event_dict = event.dict(exclude_unset=True)
        event_dict["attachments"] = ",".join(new_attachments)
    else:
        event_dict = event.dict(exclude_unset=True)
    
    # Update event fields
    for key, value in event_dict.items():
        setattr(db_event, key, value)
    
    db.commit()
    db.refresh(db_event)
    
    # Return the event with attachments as a list
    db_event.attachments = db_event.attachments.split(",") if db_event.attachments else []
    return db_event

@router.put("/{event_id}/status", response_model=Event)
async def update_event_status(
    event_id: int,
    status_update: EventStatusUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    db_event = db.query(DBEvent).filter(
        DBEvent.id == event_id,
        DBEvent.tenant_id == current_user.tenant_id
    ).first()
    
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Update status
    db_event.status = status_update.status
    
    db.commit()
    db.refresh(db_event)
    
    # Return the event with attachments as a list
    db_event.attachments = db_event.attachments.split(",") if db_event.attachments else []
    return db_event

@router.get("/events/{event_id}/pdf", response_class=StreamingResponse)
async def get_event_pdf(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    event = db.query(DBEvent).filter(
        DBEvent.id == event_id,
        DBEvent.tenant_id == current_user.tenant_id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Convert attachments string to list
    event.attachments = event.attachments.split(",") if event.attachments else []
    
    # Generate PDF
    pdf_bytes = generate_event_pdf(event)
    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=event_{event_id}.pdf"}
    )

@router.get("/events/csv")
async def get_events_csv(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Get events from database
    events = db.query(DBEvent).filter(
        DBEvent.tenant_id == current_user.tenant_id
    ).offset(offset).limit(limit).all()
    
    # Define headers for CSV
    headers = [
        "id", "contact_name", "contact_number", "description", "email",
        "event_date", "event_name", "expected_audience", "fees", "institute_name",
        "is_paid_event", "location", "payment_status", "travel_accomodation",
        "website", "attachments", "status"
    ]
    
    # Define field mapping for special handling
    field_mapping = {
        "attachments": "attachments"  # This will be handled specially
    }
    
    # Generate CSV using the utility function
    return await generate_model_csv(
        models=events,
        headers=headers,
        field_mapping=field_mapping,
        filename="events.csv"
    )

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
            await delete_object(AWS_S3_BUCKET, s3_key)
        except Exception as e:
            # Log the error but continue with the deletion
            print(f"Error deleting attachment from S3: {str(e)}")

@router.delete("/{event_id}", response_model=dict)
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # Check if event exists and belongs to user's tenant
    event = db.query(DBEvent).filter(
        DBEvent.id == event_id,
        DBEvent.tenant_id == current_user.tenant_id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Delete attachments from S3
    await delete_entity_attachments(event)
    
    # Delete the event
    db.delete(event)
    db.commit()
    
    return {"message": "Event deleted successfully"}