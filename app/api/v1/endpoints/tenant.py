from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Dict, Any
from datetime import datetime
from app.db.repository.tenants import TenantsRepository
from app.db.repository.roles import RolesRepository
from app.db.repository.permissions import PermissionsRepository
from app.schemas.tenant import (
    Tenant as TenantSchema,
    TenantCreate,
    TenantUpdate,
    TenantWithRoles,
    Role as RoleSchema,
    RoleCreate,
    RoleUpdate,
    Permission as PermissionSchema,
    PermissionCreate
)
from app.core.security import get_current_user
from app.models.user import User as DBUser
from app.utils.s3 import create_s3_bucket


router = APIRouter()

tenants_repo = TenantsRepository()
roles_repo = RolesRepository()
permissions_repo = PermissionsRepository()

# Tenant endpoints
@router.get("/tenants", response_model=List[TenantSchema])
async def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all tenants (admin only)
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    tenants = await tenants_repo.find_many({}, skip=skip, limit=limit)
    transformed_tenants = []
    for t in tenants:
        # Transform MongoDB '_id' to 'id' for Pydantic
        tenant_dict = dict(t)
        tenant_dict["id"] = tenant_dict.pop("_id")
        # Ensure created_at exists with a valid datetime
        if "created_at" not in tenant_dict or tenant_dict["created_at"] is None:
            tenant_dict["created_at"] = datetime.utcnow()
        transformed_tenants.append(tenant_dict)
    
    return [TenantSchema(**t) for t in transformed_tenants]

@router.get("/tenants/{tenant_id}", response_model=TenantWithRoles)
async def get_tenant(
    tenant_id: str = Path(..., title="Tenant ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get a specific tenant by ID (admin only or tenant admin)
    """
    if current_user["role"] != "admin" and current_user["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    tenant = await tenants_repo.find_one({"_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Transform MongoDB '_id' to 'id' for Pydantic
    tenant_dict = dict(tenant)
    tenant_dict["id"] = tenant_dict.pop("_id")
    # Ensure created_at exists with a valid datetime
    if "created_at" not in tenant_dict or tenant_dict["created_at"] is None:
        tenant_dict["created_at"] = datetime.utcnow()
    
    return TenantWithRoles(**tenant_dict)

@router.post("/tenants", response_model=TenantSchema)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new tenant (admin only)
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    new_tenant = tenant_data.dict()
    # Add created_at if not provided
    if "created_at" not in new_tenant or new_tenant["created_at"] is None:
        new_tenant["created_at"] = datetime.utcnow()
        
    inserted_id = await tenants_repo.insert_one(new_tenant)
    bucket_name = f"AWS_S3_BUCKET_{inserted_id}"
    await create_s3_bucket(bucket_name)
    created = await tenants_repo.find_one({"_id": inserted_id})
    
    # Transform MongoDB '_id' to 'id' for Pydantic
    tenant_dict = dict(created)
    tenant_dict["id"] = tenant_dict.pop("_id")
    # Ensure created_at exists with a valid datetime
    if "created_at" not in tenant_dict or tenant_dict["created_at"] is None:
        tenant_dict["created_at"] = datetime.utcnow()
    
    return TenantSchema(**tenant_dict)

@router.put("/tenants/{tenant_id}", response_model=TenantSchema)
async def update_tenant(
    tenant_id: str,
    tenant_data: TenantUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update a tenant (admin only)
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    await tenants_repo.update_one({"_id": tenant_id}, tenant_data.dict(exclude_unset=True))
    updated = await tenants_repo.find_one({"_id": tenant_id})
    if not updated:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Transform MongoDB '_id' to 'id' for Pydantic
    tenant_dict = dict(updated)
    tenant_dict["id"] = tenant_dict.pop("_id")
    # Ensure created_at exists with a valid datetime
    if "created_at" not in tenant_dict or tenant_dict["created_at"] is None:
        tenant_dict["created_at"] = datetime.utcnow()
    
    return TenantSchema(**tenant_dict)

@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a tenant (admin only)
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check if it's the default tenant (ID 1)
    if tenant_id == "1":
        raise HTTPException(status_code=400, detail="Cannot delete the default tenant")
    
    result = await tenants_repo.delete_one({"_id": tenant_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {"message": "Tenant deleted successfully"}

# Role endpoints
@router.get("/tenants/{tenant_id}/roles", response_model=List[RoleSchema])
async def list_tenant_roles(
    tenant_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all roles for a specific tenant
    """
    if current_user["role"] != "admin" and current_user["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    roles = await roles_repo.find_many({"tenant_id": tenant_id})
    transformed_roles = []
    for r in roles:
        # Transform MongoDB '_id' to 'id' for Pydantic
        role_dict = dict(r)
        role_dict["id"] = role_dict.pop("_id")
        transformed_roles.append(role_dict)
    
    return [RoleSchema(**r) for r in transformed_roles]

@router.post("/tenants/{tenant_id}/roles", response_model=RoleSchema)
async def create_tenant_role(
    tenant_id: str,
    role_data: RoleCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new role for a tenant
    """
    if current_user["role"] != "admin" and current_user["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Ensure the tenant exists
    tenant = await tenants_repo.find_one({"_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Create the role
    doc = role_data.dict()
    doc["tenant_id"] = tenant_id
    inserted_id = await roles_repo.insert_one(doc)
    created_role = await roles_repo.find_one({"_id": inserted_id})
    
    # Transform MongoDB '_id' to 'id' for Pydantic
    role_dict = dict(created_role)
    role_dict["id"] = role_dict.pop("_id")
    
    return RoleSchema(**role_dict)

@router.put("/roles/{role_id}", response_model=RoleSchema)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update a role
    """
    # Get the role
    role = await roles_repo.find_one({"_id": role_id})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check permissions
    if current_user["role"] != "admin" and current_user["tenant_id"] != role["tenant_id"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Update basic fields
    await roles_repo.update_one({"_id": role_id}, role_data.dict(exclude_unset=True))
    updated = await roles_repo.find_one({"_id": role_id})
    if not updated:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Transform MongoDB '_id' to 'id' for Pydantic
    role_dict = dict(updated)
    role_dict["id"] = role_dict.pop("_id")
    
    return RoleSchema(**role_dict)

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a role
    """
    # Get the role
    updated = await roles_repo.find_one({"_id": role_id})
    if not updated:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check permissions
    if current_user["role"] != "admin" and current_user["tenant_id"] != updated["tenant_id"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    result = await roles_repo.delete_one({"_id": role_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return {"message": "Role deleted successfully"}

# Permission endpoints
@router.get("/permissions", response_model=List[PermissionSchema])
async def list_permissions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all permissions
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    permissions = await permissions_repo.find_many({})
    transformed_permissions = []
    for p in permissions:
        # Transform MongoDB '_id' to 'id' for Pydantic
        perm_dict = dict(p)
        perm_dict["id"] = perm_dict.pop("_id")
        transformed_permissions.append(perm_dict)
    
    return [PermissionSchema(**p) for p in transformed_permissions]

@router.post("/permissions", response_model=PermissionSchema)
async def create_permission(
    permission_data: PermissionCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new permission (admin only)
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    inserted_id = await permissions_repo.insert_one(permission_data.dict())
    new_perm = await permissions_repo.find_one({"_id": inserted_id})
    
    # Transform MongoDB '_id' to 'id' for Pydantic
    perm_dict = dict(new_perm)
    perm_dict["id"] = perm_dict.pop("_id")
    
    return PermissionSchema(**perm_dict)