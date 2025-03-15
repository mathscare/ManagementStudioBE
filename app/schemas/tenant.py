from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

# Permission schemas
class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class Permission(PermissionBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

# Role schemas
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_id: int

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None

class Role(RoleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    permissions: List[Permission] = []
    
    model_config = ConfigDict(from_attributes=True)

# Tenant schemas
class TenantBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class Tenant(TenantBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class TenantWithRoles(Tenant):
    roles: List[Role] = []
    
    model_config = ConfigDict(from_attributes=True) 