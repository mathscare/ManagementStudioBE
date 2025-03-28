from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from app.db.repository.users import UsersRepository
from app.db.repository.tenants import TenantsRepository
from app.db.repository.roles import RolesRepository
from app.schemas.user import UserResponse, UserWithDetails, UserRoleUpdate
from app.core.security import get_current_user

router = APIRouter()

users_repo = UsersRepository()
tenants_repo = TenantsRepository()
roles_repo = RolesRepository()

@router.get("/", response_model=List[UserResponse])
async def get_users(
    offset: int = 0,
    limit: int = Query(default=10, le=20),  # Set max limit to 20
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    users = await users_repo.find_many({"tenant_id": tenant_id}, limit=limit, skip=offset)
    
    return [
        UserResponse(
            _id=user["_id"] if "_id" in user else user.get("id"),
            username=user["username"],
            email=user["email"],
            role="admin" if user.get("role_id") else "user"
        ) for user in users
    ]

@router.get("/{user_id}", response_model=UserWithDetails)
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    user = await users_repo.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = await roles_repo.find_one({"_id": user["role_id"]}) if user.get("role_id") else None
    
    return UserWithDetails(
        _id=user["_id"] if "_id" in user else user.get("id"),
        username=user["username"],
        email=user["email"],
        role=role["name"] if role else "user",
        tenant_id=user["tenant_id"],
        role_id=user.get("role_id")
    )

@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(user_id: str, role_update: UserRoleUpdate, current_user: dict = Depends(get_current_user)):
    user = await users_repo.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = await roles_repo.find_one({"_id": str(role_update.role_id)})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    await users_repo.update_one(
        {"_id": user_id},
        {"role_id": str(role_update.role_id)}
    )
    
    updated_user = await users_repo.find_one({"_id": user_id})
    
    return UserResponse(
        _id=updated_user["_id"] if "_id" in updated_user else updated_user.get("id"),
        username=updated_user["username"],
        email=updated_user["email"],
        role=role["name"]
    )

@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    user = await users_repo.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await users_repo.delete_one({"_id": user_id})
    
    return {"detail": "User deleted successfully"}

@router.get("/me", response_model=UserWithDetails)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Get current user information with tenant and role details
    """
    return current_user