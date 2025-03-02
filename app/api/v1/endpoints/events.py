from fastapi import APIRouter, Depends, HTTPException, UploadFile, File,Body,Query
from sqlalchemy.orm import Session
from typing import List
import json
from app.db.session import get_db
from app.models.event import Event as DBEvent
from app.schemas.event import EventCreate, Event, EventUpdate, EventStatusUpdate
from app.utils.s3 import upload_file_to_s3
from app.utils.pdf_generator import generate_event_pdf
from fastapi.responses import StreamingResponse
from io import BytesIO
import csv
from io import StringIO, BytesIO


router = APIRouter()

@router.post("/", response_model=Event)
async def create_event(
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


@router.get("/", response_model=List[Event])
def get_events(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db)
):
    events = db.query(DBEvent).offset(offset).limit(limit).all()
    for event in events:
        if event.attachments:
            event.attachments = event.attachments.split(",")
        else:
            event.attachments = []
    return events

@router.get("/{event_id}", response_model=Event)
def get_sinlge_event(
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
    
    # Use model_dump() with exclude_unset=True (instead of event.dict())
    update_data = event.model_dump(exclude_unset=True)
    
    if "attachments" in update_data and update_data["attachments"] is not None:
        update_data["attachments"] = ",".join(update_data["attachments"])
    
    for key, value in update_data.items():
        if key == "website" and value is not None:
            setattr(db_event, key, str(value))
        else:
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

@router.get("/events/{event_id}/pdf", response_class=StreamingResponse)
def get_event_pdf(event_id: int,
    db: Session = Depends(get_db)):
    # Retrieve event data from the database (this is just an example; adjust as needed)
    event_obj = db.query(DBEvent).filter(DBEvent.id == event_id).first()
    if not event_obj:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # For attachments, assume you have stored a comma-separated string and convert it to a list
    attachments = event_obj.attachments.split(",") if event_obj.attachments else []

    # Generate the PDF in memory
    buffer = BytesIO()
    generate_event_pdf({
        "event_name": event_obj.event_name,
        "institute_name": event_obj.institute_name,
        "event_date": event_obj.event_date,
        "location": event_obj.location,
        "website": event_obj.website,
        "contact_name": event_obj.contact_name,
        "contact_number": event_obj.contact_number,
        "email": event_obj.email,
        "description": event_obj.description,
        "expected_audience": event_obj.expected_audience,
        "fees": event_obj.fees,
        "payment_status": event_obj.payment_status,
        "travel_accomodation": event_obj.travel_accomodation,
    }, attachments, buffer)
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f"inline; filename=event_{event_id}.pdf"})

@router.get("/events/csv", response_class=StreamingResponse)
def get_events_csv(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db)
):
    # Query events from the database with offset and limit.
    events = db.query(DBEvent).offset(offset).limit(limit).all()
    
    # Create a CSV file in memory.
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header row; adjust the headers according to your model.
    headers = [
        "id", "contact_name", "contact_number", "description", "email",
        "event_date", "event_name", "expected_audience", "fees", "institute_name",
        "is_paid_event", "location", "payment_status", "travel_accomodation",
        "website", "attachments", "status"
    ]
    writer.writerow(headers)
    
    for event in events:
        # If attachments is a string, assume it's already comma-separated; if it's a list, join it.
        if event.attachments:
            try:
                # If attachments is already a list (from earlier processing)
                attachments_str = ",".join(event.attachments)
            except Exception:
                attachments_str = event.attachments
        else:
            attachments_str = ""
        
        writer.writerow([
            event.id,
            event.contact_name,
            event.contact_number,
            event.description,
            event.email,
            event.event_date,
            event.event_name,
            event.expected_audience,
            event.fees,
            event.institute_name,
            event.is_paid_event,
            event.location,
            event.payment_status,
            event.travel_accomodation,
            str(event.website) if event.website else "",
            attachments_str,
            event.status
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    # Create a BytesIO stream from CSV content.
    buffer = BytesIO(csv_content.encode("utf-8"))
    
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=events.csv"}
    )

@router.delete("/{event_id}", response_model=dict)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(db_event)
    db.commit()
    return {"message": f"Event with id {event_id} deleted successfully."}