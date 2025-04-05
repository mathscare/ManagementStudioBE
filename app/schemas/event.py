from datetime import date
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from uuid import UUID

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
    is_camera_man_hired: Optional[bool] = False
    camera_man_name: Optional[str] = None
    camera_man_number: Optional[str] = None

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
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
    is_camera_man_hired: Optional[bool] = None
    camera_man_name: Optional[str] = None
    camera_man_number: Optional[str] = None

class EventStatusUpdate(BaseModel):
    status: str

class Event(EventBase):
    id: UUID

# New schema classes for email extraction
class EmailTextRequest(BaseModel):
    """Request model for extracting event details from email text"""
    email_text: str

class AIExtractedField(BaseModel):
    """Represents a field extracted by AI with confidence level"""
    value: Optional[str] = None
    confidence: float = 0.0

class AIEventExtraction(BaseModel):
    """Structured format for AI extraction results"""
    contact_name: Optional[str] = None
    contact_number: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    event_date: Optional[str] = None
    event_name: Optional[str] = None
    expected_audience: Optional[int] = None
    fees: Optional[float] = None
    institute_name: Optional[str] = None
    is_paid_event: Optional[bool] = None
    location: Optional[str] = None
    payment_status: Optional[str] = None
    travel_accomodation: Optional[str] = None
    website: Optional[str] = None
    is_camera_man_hired: Optional[bool] = None
    camera_man_name: Optional[str] = None
    camera_man_number: Optional[str] = None
