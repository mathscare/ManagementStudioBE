from fastapi import APIRouter, Depends, HTTPException, status, Header, File, UploadFile, Form
from pydantic import BaseModel
from datetime import timedelta
from typing import Optional
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import create_access_token, pwd_context
from app.db.repository.users import UsersRepository
from app.db.repository.tenants import TenantsRepository
from app.db.repository.roles import RolesRepository
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.core.config import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from uuid import UUID, uuid4
from app.utils.s3 import create_s3_bucket, upload_file_to_s3
import io
from datetime import datetime


router = APIRouter()
ACCESS_TOKEN_EXPIRE_MINUTES = 30

users_repo = UsersRepository()
tenants_repo = TenantsRepository()
roles_repo = RolesRepository()

class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: UUID


@router.post("/signup/", response_model=UserResponse)
async def signup(
    user: UserCreate = Depends(),
    profile_pic: Optional[UploadFile] = File(None)
):
    query = {
        "$and": [
            {"tenant_id": str(user.tenant_id)} if user.tenant_id else {},
            {"$or": [{"username": user.username}, {"email": user.email}]}
        ]
    }
    existing_user = await users_repo.find_one(query)
    if existing_user:
        if existing_user["username"] == user.username:
            raise HTTPException(status_code=400, detail="Username already registered for this tenant")
        if existing_user["email"] == user.email:
            raise HTTPException(status_code=400, detail="Email already registered for this tenant")

    hashed_password = pwd_context.hash(user.password)
    
    tenant_id = user.tenant_id
    if not tenant_id:
        tenant_id = uuid4() 
        tenant = {
            "_id": str(tenant_id),
            "name": user.organization_name,
            "description": f"Tenant for {user.organization_name}",
            "created_at" : datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True
        }
        await tenants_repo.insert_one(tenant)
        bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
        await create_s3_bucket(bucket_name)
    
    role_id = user.role_id
    if role_id:
        existing_role = await roles_repo.find_one({"_id": str(role_id), "tenant_id": str(tenant_id)})
        if not existing_role:
            raise HTTPException(status_code=400, detail="Invalid role_id for the specified tenant")
    else:
        user_role = await roles_repo.find_one({"name": "user", "tenant_id": str(tenant_id)})
        if not user_role:
            role_id = uuid4()
            user_role = {
                "_id": str(role_id),
                "name": "user",
                "description": "Default user role for the tenant",
                "tenant_id": str(tenant_id),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await roles_repo.insert_one(user_role)
        else:
            role_id = UUID(user_role["_id"])

    # Handle profile picture upload
    profile_pic_url = None
    if profile_pic:
        user_id = str(uuid4())
        bucket_name = f"AWS_S3_BUCKET_{tenant_id}"
        file_extension = profile_pic.filename.split('.')[-1]
        file_key = f"profile_pics/{user_id}.{file_extension}"
        
        profile_pic_url = await upload_file_to_s3(
            file=profile_pic,
            key=file_key,
            bucket=bucket_name
        )

    new_user = {
        "_id": str(uuid4()),
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_password,
        "role_id": str(role_id),
        "tenant_id": str(tenant_id),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "guardian": user.guardian,
        "guardian_number": user.guardian_number,
        "city": user.city,
        "state": user.state,
        "country": user.country,
        "address_line1": user.address_line1,
        "address_line2": user.address_line2,
        "pincode": user.pincode,
        "aadhar_card_number": user.aadhar_card_number,
        "bank_name": user.bank_name,
        "account_number": user.account_number,
        "ifsc_code": user.ifsc_code,
        "profile_pic_url": profile_pic_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_active": True
    }

    await users_repo.insert_one(new_user)
    
    # Get the role name for the response
    role = await roles_repo.find_one({"_id": str(role_id)})
    role_name = role["name"] if role else "user"
    
    return UserResponse(
        _id=new_user["_id"],
        username=new_user["username"],
        email=new_user["email"],
        role=role_name,
        tenant_id=new_user["tenant_id"],
        role_id=new_user["role_id"],
        first_name=new_user.get("first_name"),
        last_name=new_user.get("last_name"),
        phone_number=new_user.get("phone_number"),
        guardian=new_user.get("guardian"),
        guardian_number=new_user.get("guardian_number"),
        city=new_user.get("city"),
        state=new_user.get("state"),
        country=new_user.get("country"),
        address_line1=new_user.get("address_line1"),
        address_line2=new_user.get("address_line2"),
        pincode=new_user.get("pincode"),
        aadhar_card_number=new_user.get("aadhar_card_number"),
        bank_name=new_user.get("bank_name"),
        account_number=new_user.get("account_number"),
        ifsc_code=new_user.get("ifsc_code"),
        profile_pic_url=new_user.get("profile_pic_url")
    )

@router.post("/login/", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    tenant_id: str = Header(..., description="Tenant ID for authentication")
):
    try:
        tenant_id_str = tenant_id
        user = await users_repo.find_one({"username": form_data.username, "tenant_id": tenant_id_str})
        if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        role = await roles_repo.find_one({"_id": user["role_id"]}) if user.get("role_id") else None
        token_data = {
            "sub": user["username"], 
            "tenant_id": user["tenant_id"],
            "role": role["name"] if role else None
        }
        
        if "role_id" in user:
            token_data["role_id"] = user["role_id"]
        
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        refresh_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 336)
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": role["name"] if role else None, 
            "refresh_token": refresh_token
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication failed: {str(e)}")

@router.post("/swagger-login/", response_model=Token, description="Login endpoint for Swagger UI - automatically identifies tenant")
async def swagger_login(login_data: OAuth2PasswordRequestForm = Depends()):
    try:
        # Find the user by username only
        user = await users_repo.find_one({"username": login_data.username})
        if not user or not pwd_context.verify(login_data.password, user["hashed_password"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        # Get tenant_id from the user record
        tenant_id = user["tenant_id"]
        
        role = await roles_repo.find_one({"_id": user["role_id"]}) if user.get("role_id") else None
        token_data = {
            "sub": user["username"], 
            "tenant_id": tenant_id,
            "role": role["name"] if role else None
        }
        
        if "role_id" in user:
            token_data["role_id"] = user["role_id"]
        
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        refresh_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 336)
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": role["name"] if role else None, 
            "refresh_token": refresh_token
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication failed: {str(e)}")

@router.post("/refresh/", response_model=Token)
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        
        if username is None or tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = await users_repo.find_one({"username": username, "tenant_id": tenant_id})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        role = await roles_repo.find_one({"_id": user["role_id"]}) if user.get("role_id") else None
        token_data = {
            "sub": user["username"], 
            "tenant_id": user["tenant_id"],
            "role": role["name"] if role else None
        }
        
        if "role_id" in user:
            token_data["role_id"] = user["role_id"]
            
        new_access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return {
            "access_token": new_access_token, 
            "token_type": "bearer",
            "role": role["name"] if role else None,
            "refresh_token": refresh_token
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")