from fastapi import APIRouter, Depends, HTTPException, UploadFile, File,Body
from sqlalchemy.orm import Session
from typing import List
import json
from app.db.session import get_db
from app.models.event import Event as DBEvent
from app.schemas.event import EventCreate, Event, EventUpdate, EventStatusUpdate
from app.utils.s3 import upload_file_to_s3


router = APIRouter()


from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.event import Event as DBEvent  # Your ORM model
from app.schemas.event import EventCreate, Event  # Pydantic models for input and output

router = APIRouter()

@router.post("/", response_model=Event)
async def create_event_form(
    event_data: EventCreate = Body(...),  # Now expecting a JSON body
    db: Session = Depends(get_db)
):
    # Create a new event record in the database without any file processing
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
        attachments="",  # No attachments initially
        status=event_data.status
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # For response, convert attachments string to list
    db_event.attachments = db_event.attachments.split(",") if db_event.attachments else []
    return db_event

@router.get("/", response_model=List[Event])
def get_events(db: Session = Depends(get_db)):
    events = db.query(DBEvent).all()
    for event in events:
        if event.attachments:
            event.attachments = event.attachments.split(",")
        else:
            event.attachments = []
    return events

@router.get("/{event_id}", response_model=Event)
def get_events(
    event_id: int,
    db: Session = Depends(get_db)):
    event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
    if event.attachments:
        event.attachments = event.attachments.split(",")
    else:
        event.attachments = []
    return event

@router.put("/{event_id}/form", response_model=Event)
def update_event_form(
    event_id: int,
    event: EventUpdate,
    db: Session = Depends(get_db)
):
    db_event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    update_data = event.dict(exclude_unset=True)
    if "attachments" in update_data and update_data["attachments"] is not None:
        update_data["attachments"] = ",".join(update_data["attachments"])
    for key, value in update_data.items():
        setattr(db_event, key, value)
    db.commit()
    db.refresh(db_event)
    if db_event.attachments:
        db_event.attachments = db_event.attachments.split(",")
    else:
        db_event.attachments = []
    return db_event

@router.put("/{event_id}/status", response_model=Event)
def update_event_status(
    event_id: int,
    status_update: EventStatusUpdate,
    db: Session = Depends(get_db)
):
    db_event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    db_event.status = status_update.status
    db.commit()
    db.refresh(db_event)
    if db_event.attachments:
        db_event.attachments = db_event.attachments.split(",")
    else:
        db_event.attachments = []
    return db_event

@router.post("/{event_id}/attachments", response_model=Event)
async def add_event_attachments(
    event_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    # Fetch the event record; if not found, return 404
    db_event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get any existing attachments (assumed stored as a comma-separated string)
    existing_attachments = db_event.attachments.split(",") if db_event.attachments else []
    
    # Process each uploaded file: upload and collect URLs
    new_attachment_urls = []
    for file in files:
        url = upload_file_to_s3(file, db_event.event_name)
        new_attachment_urls.append(url)
    
    # Append new attachments to existing ones
    all_attachments = existing_attachments + new_attachment_urls
    db_event.attachments = ",".join(all_attachments)
    
    db.commit()
    db.refresh(db_event)
    
    # Return the event with attachments as a list
    db_event.attachments = db_event.attachments.split(",") if db_event.attachments else []
    return db_event
