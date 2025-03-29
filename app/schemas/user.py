from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from app.schemas.tenant import Role, Tenant
from datetime import datetime

class UserResponse(BaseModel):
    id: UUID = Field(alias="_id")
    username: str
    email: EmailStr
    role: str = "user"
    tenant_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    guardian: Optional[str] = None
    guardian_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    pincode: Optional[str] = None
    aadhar_card_number: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {UUID: str}
        allow_population_by_field_name = True

class UserWithDetails(UserResponse):
    pass

class UserWithDetailstoken(BaseModel):
    id: str
    role : str = "user"
    tenant_id: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    organization_name: str  
    role_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    guardian: Optional[str] = None
    guardian_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    pincode: Optional[str] = None
    aadhar_card_number: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None

class RoleUpdate(BaseModel):
    role: UUID

class UserRoleUpdate(BaseModel):
    role_id: UUID

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    guardian: Optional[str] = None
    guardian_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    pincode: Optional[str] = None
    aadhar_card_number: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
