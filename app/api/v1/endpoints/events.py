from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.event import Event as DBEvent
from app.schemas.event import EventCreate, Event, EventUpdate

router = APIRouter()

@router.post("/", response_model=Event)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    # Convert attachments list to a comma-separated string if provided
    attachments_str = ",".join(event.attachments) if event.attachments else ""
    
    db_event = DBEvent(
        contact_name=event.contact_name,
        contact_number=event.contact_number,
        description=event.description,
        email=event.email,
        event_date=event.event_date,
        event_name=event.event_name,
        expected_audience=event.expected_audience,
        fees=event.fees,
        institute_name=event.institute_name,
        is_paid_event=event.is_paid_event,
        location=event.location,
        payment_status=event.payment_status,
        travel_accomodation=event.travel_accomodation,
        website=event.website,
        attachments=attachments_str,
        status=event.status if event.status else "pending"  # Use provided status or default
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    # Convert attachments back to a list
    if db_event.attachments:
        db_event.attachments = db_event.attachments.split(",")
    else:
        db_event.attachments = []
    return db_event

@router.get("/", response_model=List[Event])
def get_events(db: Session = Depends(get_db)):
    events = db.query(DBEvent).all()
    # Convert attachments string back to list
    for event in events:
        if event.attachments:
            event.attachments = event.attachments.split(",")
        else:
            event.attachments = []
    return events

@router.put("/{event_id}", response_model=Event)
def update_event(event_id: int, event: EventUpdate, db: Session = Depends(get_db)):
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
