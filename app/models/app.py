from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class File(BaseModel):
    id: UUID
    file_name: str
    s3_key: str
    created_at: Optional[str] = None
    restored_url: Optional[str] = None
    restored_url_expiration: Optional[str] = None
    tenant_id: UUID
    tags: List[UUID] = []

class Tag(BaseModel):
    id: Optional[UUID] = Field(default=None)
    name: str
    type: Optional[str] = "default"
    tenant_id: UUID
    files: List[UUID] = []

