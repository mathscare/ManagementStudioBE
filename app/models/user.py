from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from uuid import UUID

class User(BaseModel):
    id: UUID = Field(alias="_id")  # Use alias to map _id in the database to id in the model
    username: str
    email: EmailStr
    hashed_password: str
    tenant_id: UUID
    role_id: Optional[UUID] = None

    class Config:
        arbitrary_types_allowed = True
        allow_population_by_field_name = True  # Allow using both id and _id
