from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from uuid import UUID

class Event(BaseModel):
    id: UUID
    contact_name: str
    contact_number: str
    description: Optional[str] = None
    email: str
    event_date: Optional[date] = None
    event_name: str
    expected_audience: Optional[int] = None
    fees: Optional[float] = None
    institute_name: Optional[str] = None
    is_paid_event: bool = False
    location: Optional[str] = None
    payment_status: Optional[str] = None
    travel_accomodation: Optional[str] = None
    website: Optional[str] = None
    attachments: Optional[str] = None
    status: str = "pending"
    tenant_id: UUID
    is_camera_man_hired: bool = False
    camera_man_name: Optional[str] = None
    camera_man_number: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
