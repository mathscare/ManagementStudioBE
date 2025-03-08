# schemas.py
from pydantic import BaseModel
from typing import List

class TagOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class FileOut(BaseModel):
    id: int
    file_name: str
    s3_key: str
    tags: List[TagOut]

    class Config:
        from_attributes = True

class FileUploadResponse(BaseModel):
    id: int
    file_name: str
    s3_key: str
    tags: List[str]
