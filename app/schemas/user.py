from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from app.schemas.tenant import Role, Tenant

class UserResponse(BaseModel):
    id: UUID = Field(alias="_id")
    username: str
    email: EmailStr
    role: str = "user"

    class Config:
        json_encoders = {UUID: str}
        allow_population_by_field_name = True

class UserWithDetails(UserResponse):
    tenant_id: Optional[UUID] = None
    role_id: Optional[UUID] = None

    class Config:
        json_encoders = {UUID: str}

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    organization_name: str  
    role_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None

class RoleUpdate(BaseModel):
    role: UUID

class UserRoleUpdate(BaseModel):
    role_id: UUID
