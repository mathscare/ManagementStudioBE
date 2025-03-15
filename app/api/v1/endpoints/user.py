from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from app.schemas.user import UserResponse, UserWithDetails, RoleUpdate, UserRoleUpdate
from app.core.security import get_current_user
from app.models.user import User as DBUser
from app.models.tenant import Role, Tenant
from app.db.session import get_db

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def get_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get all users in the current tenant
    """
    users = db.query(DBUser).filter(DBUser.tenant_id == current_user.tenant_id).offset(offset).limit(limit).all()
    return users

@router.get("/with-details", response_model=List[UserWithDetails])
def get_users_with_details(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get all users in the current tenant with tenant and role details
    """
    users = (
        db.query(DBUser)
        .filter(DBUser.tenant_id == current_user.tenant_id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return users

@router.get("/me", response_model=UserWithDetails)
def read_users_me(current_user: DBUser = Depends(get_current_user)):
    """
    Get current user information with tenant and role details
    """
    return current_user

@router.get("/{user_id}", response_model=UserWithDetails)
def get_user(
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Get a specific user by ID
    """
    # Only allow users from the same tenant or admins
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.tenant_id != current_user.tenant_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return user

@router.delete("/{user_id}", response_model=UserResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Delete a user by ID. Only admins can perform this action.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete users")
    
    user = db.query(DBUser).filter(
        DBUser.id == user_id,
        DBUser.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    
    return user

@router.put("/{user_id}/role", response_model=UserWithDetails)
def update_user_role(
    user_id: int,
    role_update: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Update a user's role string (admin, user, etc.)
    """
    # Ensure only admins can update roles
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update roles")

    # Fetch the user to be updated
    user = db.query(DBUser).filter(
        DBUser.id == user_id,
        DBUser.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update the role
    user.role = role_update.role
    db.commit()
    db.refresh(user)

    return user

@router.put("/{user_id}/assign-role", response_model=UserWithDetails)
def assign_role_to_user(
    user_id: int,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    Assign a specific role object to a user
    """
    # Ensure only admins or tenant admins can assign roles
    if current_user.role != "admin" and current_user.role != "tenant_admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Fetch the user to be updated
    user = db.query(DBUser).filter(
        DBUser.id == user_id,
        DBUser.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify the role exists and belongs to the same tenant
    role = db.query(Role).filter(
        Role.id == role_update.role_id,
        Role.tenant_id == current_user.tenant_id
    ).first()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found or not in your tenant")

    # Assign the role to the user
    user.role_id = role.id
    db.commit()
    db.refresh(user)

    return user