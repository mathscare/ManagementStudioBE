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
    status: Optional[str] = None  # New field

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    contact_name: Optional[str]
    contact_number: Optional[str]
    description: Optional[str]
    email: Optional[str]
    event_date: Optional[date]
    event_name: Optional[str]
    expected_audience: Optional[int]
    fees: Optional[float]
    institute_name: Optional[str]
    is_paid_event: Optional[bool]
    location: Optional[str]
    payment_status: Optional[str]
    travel_accomodation: Optional[str]
    website: Optional[HttpUrl]
    attachments: Optional[List[str]]
    status: Optional[str]  # New field

class Event(EventBase):
    id: int

    class Config:
        orm_mode = True
