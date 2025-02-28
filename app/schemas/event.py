# app/schemas/event.py
from pydantic import BaseModel, HttpUrl
from datetime import date
from typing import Optional, List

class EventBase(BaseModel):
    contact_name: str
    contact_number: str
    description: Optional[str] = None
    email: str
    event_date: date
    event_name: str
    expected_audience: int
    fees: float
    institute_name: str
    is_paid_event: bool
    location: str
    payment_status: Optional[str] = None
    travel_accomodation: Optional[str] = None
    website: Optional[HttpUrl] = None
    attachments: Optional[List[str]] = None
    status: Optional[str] = None

class EventCreate(BaseModel):
    travel_accomodation: str
    contact_number: str
    contact_name: str
    payment_status: str
    expected_audience: int
    fees: float
    event_name: str
    attachments: List[str] = []  # This field is not used for file uploads; it will be replaced by S3 URLs.
    status: str
    event_date: str  # You can use a date type if you prefer
    institute_name: str
    location: str
    website: Optional[HttpUrl] = None
    is_paid_event: bool
    email: str
    description: str


class EventUpdate(BaseModel):
    # For updating form details (status not included)
    contact_name: Optional[str] = None
    contact_number: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    event_date: Optional[date] = None
    event_name: Optional[str] = None
    expected_audience: Optional[int] = None
    fees: Optional[float] = None
    institute_name: Optional[str] = None
    is_paid_event: Optional[bool] = None
    location: Optional[str] = None
    payment_status: Optional[str] = None
    travel_accomodation: Optional[str] = None
    website: Optional[HttpUrl] = None
    attachments: Optional[List[str]] = None

class EventStatusUpdate(BaseModel):
    status: str

class Event(EventBase):
    id: int

    class Config:
        orm_mode = True
