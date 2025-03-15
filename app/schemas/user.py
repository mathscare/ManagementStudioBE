from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from app.schemas.tenant import Role, Tenant

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str = "user"
    tenant_id: int
    role_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class UserWithDetails(UserResponse):
    tenant: Optional[Tenant] = None
    role_obj: Optional[Role] = None
    
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    organization_name: str  
    role: str = "user"
    tenant_id: Optional[int] = None

class RoleUpdate(BaseModel):
    role: str

class UserRoleUpdate(BaseModel):
    role_id: int