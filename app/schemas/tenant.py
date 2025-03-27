from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class Permission(PermissionBase):
    id: UUID

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_id: UUID

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[UUID]] = None

class Role(RoleBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    permissions: List[Permission] = []

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
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

class TenantWithRoles(Tenant):
    roles: List[Role] = []
