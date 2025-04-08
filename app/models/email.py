from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class EmailAttachment(BaseModel):
    filename: str
    content_type: Optional[str] = None
    content: Optional[str] = None
    size: Optional[int] = None
    content_id: Optional[str] = None
    s3_key: Optional[str] = None
    s3_url: Optional[str] = None

class Email(BaseModel):
    id: UUID = Field(alias="_id")
    from_: str
    to: str
    subject: str
    date: Optional[str] = None
    cc: Optional[str] = None
    reply_to: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    message_id: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    body: Optional[str] = None
    html_body: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = []
    tenant_id: UUID
    created_at: datetime
    processed: bool = False
    processed_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        allow_population_by_field_name = True
