from pydantic import BaseModel, EmailStr
from typing import Optional

class UserResponse(BaseModel):
    username: str
    email: EmailStr
    role: str = "user"

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"

class RoleUpdate(BaseModel):
    role: str 