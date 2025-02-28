# app/models/event.py
from sqlalchemy import Column, Integer, String, Boolean, Date, Float, Text
from app.db.session import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    contact_name = Column(String, nullable=False)
    contact_number = Column(String, nullable=False)
    description = Column(Text)
    email = Column(String, nullable=False)
    event_date = Column(Date)
    event_name = Column(String, nullable=False)
    expected_audience = Column(Integer)
    fees = Column(Float)
    institute_name = Column(String)
    is_paid_event = Column(Boolean, default=False)
    location = Column(String)
    payment_status = Column(String)
    travel_accomodation = Column(String)
    website = Column(String)
    attachments = Column(Text)
    status = Column(String, default="pending")
