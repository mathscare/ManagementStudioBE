from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# ----------------------------
# Tenant Model
# ----------------------------
class Tenant(BaseModel):
    id: UUID = Field(alias="_id")  # Use alias to map _id in the database to id in the model
    name: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        allow_population_by_field_name = True  # Allow using both id and _id

# ----------------------------
# Role Model
# ----------------------------
class Role(BaseModel):
    id: Optional[UUID] = Field(default=None, alias="_id")  # Use alias to map _id in the database to id in the model
    name: str
    description: Optional[str] = None
    tenant_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ----------------------------
# Permission Model
# ----------------------------
class Permission(BaseModel):
    id: Optional[UUID] = Field(default=None, alias="_id")  # Use alias to map _id in the database to id in the model
    name: str
    description: Optional[str] = None

