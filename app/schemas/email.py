from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class Attachment(BaseModel):
    """Email attachment model"""
    filename: str
    content_type: Optional[str] = None
    content: Optional[str] = None  # Base64 encoded content - only used for upload, not stored
    size: Optional[int] = None
    content_id: Optional[str] = None
    s3_key: Optional[str] = None
    s3_url: Optional[str] = None
    
    @validator('content')
    def validate_base64(cls, v):
        """Validate that content is valid base64 if present"""
        import base64
        if v:
            try:
                # Just testing if it's valid base64
                base64.b64decode(v)
            except Exception:
                raise ValueError("Attachment content must be valid base64")
        return v

    class Config:
        # Exclude content field from response models by default
        exclude = {"content"}

class EmailData(BaseModel):
    """Email data model for incoming emails"""
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
    attachments: Optional[List[Attachment]] = []

class EmailResponse(BaseModel):
    """Response model for emails"""
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
    body: Optional[str] = None
    html_body: Optional[str] = None
    attachments: Optional[List[Attachment]] = []
    tenant_id: UUID
    created_at: datetime
    processed: bool = False
    processed_at: Optional[datetime] = None
    
    class Config:
        allow_population_by_field_name = True
        json_encoders = {UUID: str}
