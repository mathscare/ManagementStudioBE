# schemas.py
from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime


class TagOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class FileOut(BaseModel):
    id: int
    file_name: str
    s3_key: str
    created_at: datetime 
    tags: List[TagOut]

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    id: int
    file_name: str
    s3_key: str
    tags: List[str]
