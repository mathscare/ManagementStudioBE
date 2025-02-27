from fastapi import APIRouter, Depends
from app.schemas.user import UserResponse
from app.core.security import get_current_user
from app.models.user import User as DBUser

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: DBUser = Depends(get_current_user)):
    return current_user
