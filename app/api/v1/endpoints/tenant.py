from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.tenant import Tenant, Role, Permission
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
from sqlalchemy.exc import IntegrityError

router = APIRouter()

# Tenant endpoints
@router.get("/tenants", response_model=List[TenantSchema])
def get_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get all tenants (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    tenants = db.query(Tenant).offset(skip).limit(limit).all()
    return tenants

@router.get("/tenants/{tenant_id}", response_model=TenantWithRoles)
def get_tenant(
    tenant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get a specific tenant by ID (admin only or tenant admin)
    """
    if current_user.role != "admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return tenant

@router.post("/tenants", response_model=TenantSchema)
def create_tenant(
    tenant: TenantCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Create a new tenant (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        db_tenant = Tenant(**tenant.model_dump())
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        
        # Create a default admin role for this tenant
        admin_role = Role(
            name="tenant_admin",
            description="Default administrator role for the tenant",
            tenant_id=db_tenant.id
        )
        db.add(admin_role)
        db.commit()
        
        return db_tenant
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tenant with this name already exists")

@router.put("/tenants/{tenant_id}", response_model=TenantSchema)
def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Update a tenant (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    update_data = tenant_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tenant, key, value)
    
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

@router.delete("/tenants/{tenant_id}")
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Delete a tenant (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check if it's the default tenant (ID 1)
    if tenant_id == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the default tenant")
    
    db_tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check if there are users in this tenant
    user_count = db.query(DBUser).filter(DBUser.tenant_id == tenant_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete tenant with active users. Transfer or delete {user_count} users first."
        )
    
    db.delete(db_tenant)
    db.commit()
    return {"message": "Tenant deleted successfully"}

# Role endpoints
@router.get("/tenants/{tenant_id}/roles", response_model=List[RoleSchema])
def get_tenant_roles(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get all roles for a specific tenant
    """
    if current_user.role != "admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    roles = db.query(Role).filter(Role.tenant_id == tenant_id).all()
    return roles

@router.post("/tenants/{tenant_id}/roles", response_model=RoleSchema)
def create_tenant_role(
    tenant_id: int,
    role: RoleCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Create a new role for a tenant
    """
    if current_user.role != "admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Ensure the tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Create the role
    db_role = Role(**role.model_dump())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    return db_role

@router.put("/roles/{role_id}", response_model=RoleSchema)
def update_role(
    role_id: int,
    role_update: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Update a role
    """
    # Get the role
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check permissions
    if current_user.role != "admin" and current_user.tenant_id != db_role.tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Update basic fields
    update_data = role_update.model_dump(exclude={"permission_ids"}, exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_role, key, value)
    
    # Update permissions if provided
    if role_update.permission_ids is not None:
        # Clear existing permissions
        db_role.permissions = []
        
        # Add new permissions
        for perm_id in role_update.permission_ids:
            permission = db.query(Permission).filter(Permission.id == perm_id).first()
            if permission:
                db_role.permissions.append(permission)
    
    db.commit()
    db.refresh(db_role)
    return db_role

@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Delete a role
    """
    # Get the role
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check permissions
    if current_user.role != "admin" and current_user.tenant_id != db_role.tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check if users are assigned to this role
    user_count = db.query(DBUser).filter(DBUser.role_id == role_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role with assigned users. Reassign {user_count} users first."
        )
    
    db.delete(db_role)
    db.commit()
    return {"message": "Role deleted successfully"}

# Permission endpoints
@router.get("/permissions", response_model=List[PermissionSchema])
def get_permissions(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get all permissions
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    permissions = db.query(Permission).all()
    return permissions

@router.post("/permissions", response_model=PermissionSchema)
def create_permission(
    permission: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Create a new permission (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        db_permission = Permission(**permission.model_dump())
        db.add(db_permission)
        db.commit()
        db.refresh(db_permission)
        return db_permission
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Permission with this name already exists") 