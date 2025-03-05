from pydantic import BaseModel, EmailStr
from typing import Optional

class UserResponse(BaseModel):
    username: str
    email: EmailStr
    role: Optional[str] = "user"

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: Optional[str] = "user"

class RoleUpdate(BaseModel):
    role: str 