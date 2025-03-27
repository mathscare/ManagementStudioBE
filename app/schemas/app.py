from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime
from uuid import UUID

class TagOut(BaseModel):
    id: UUID
    name: str
    type: str

    class Config:
        populate_by_name = True

class FileOut(BaseModel):
    id: UUID
    file_name: str
    s3_key: str
    created_at: datetime
    tags: List[UUID]

    class Config:
        populate_by_name = True

class FileUploadResponse(BaseModel):
    id: UUID
    file_name: str
    s3_key: str
    tags: List[UUID]

class TagInput(BaseModel):
    tags: Dict[str, List[str]]
