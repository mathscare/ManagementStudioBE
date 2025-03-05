from fastapi import APIRouter, Depends,Query
from app.schemas.user import UserResponse
from app.core.security import get_current_user
from app.models.user import User as DBUser
from app.schemas.user import RoleUpdate,UserResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from typing import List



router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def get_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    users = db.query(DBUser).offset(offset).limit(limit).all()

    return users

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: DBUser = Depends(get_current_user)):
    return current_user

@router.delete("/delete/{user_name}", response_model=UserResponse)
def delete_user(user_name: str, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """
    Delete a user by ID. Only admins can perform this action.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete users")
    
    user = db.query(DBUser).filter(DBUser.username == user_name).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    
    return user

@router.put("/admin/update-role/{user_name}")
def update_user_role(
    user_name: str,
    role_update: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    # Ensure only admins can update roles
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update roles")

    # Fetch the user to be updated
    user = db.query(DBUser).filter(DBUser.username == user_name).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update the role
    user.role = role_update.role
    db.commit()
    db.refresh(user)

    return {"message": "User role updated successfully", "user_name": user.username, "new_role": user.role}