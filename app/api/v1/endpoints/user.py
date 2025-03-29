from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form, status
from typing import List, Optional
from app.db.repository.users import UsersRepository
from app.db.repository.tenants import TenantsRepository
from app.db.repository.roles import RolesRepository
from app.schemas.user import UserResponse, UserWithDetails, UserRoleUpdate, UserProfileUpdate,UserWithDetailstoken
from app.core.security import get_current_user
from app.utils.s3 import upload_file_to_s3
import io
from datetime import datetime
from pydantic import parse_obj_as

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
    
    result = []
    for user in users:
        role = await roles_repo.find_one({"_id": user.get("role_id")}) if user.get("role_id") else None
        role_name = role["name"] if role else "user"
        
        user_response = UserResponse(
            _id=user["_id"] if "_id" in user else user.get("id"),
            username=user["username"],
            email=user["email"],
            role=role_name,
            tenant_id=user.get("tenant_id"),
            role_id=user.get("role_id"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            phone_number=user.get("phone_number"),
            guardian=user.get("guardian"),
            guardian_number=user.get("guardian_number"),
            city=user.get("city"),
            state=user.get("state"),
            country=user.get("country"),
            address_line1=user.get("address_line1"),
            address_line2=user.get("address_line2"),
            pincode=user.get("pincode"),
            aadhar_card_number=user.get("aadhar_card_number"),
            bank_name=user.get("bank_name"),
            account_number=user.get("account_number"),
            ifsc_code=user.get("ifsc_code"),
            profile_pic_url=user.get("profile_pic_url"),
            is_active=user.get("is_active"),
            created_at=user.get("created_at"),
            updated_at=user.get("updated_at")
        )
        result.append(user_response)
    
    return result

@router.get("/me", response_model=UserWithDetails)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Get current user information with tenant and role details
    """
    print(f"Current user data from token: {current_user}")
    
    # Get the user ID directly from the token
    user_id = current_user.get("_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identification in token"
        )
    
    print(f"Looking for user with ID from token: {user_id}")
    
    # Query using the ID from the token, not from the URL
    user = await users_repo.find_one({"_id": user_id})
    
    if not user:
        print(f"User with ID {user_id} not found in database")
        raise HTTPException(
            status_code=404, 
            detail=f"User with ID {user_id} not found in database"
        )
    
    print(f"User found: {user.get('username')}")
    role = await roles_repo.find_one({"_id": user.get("role_id")}) if user.get("role_id") else None
    
    # Return the user details
    return UserWithDetails(
        _id=user["_id"],
        username=user["username"],
        email=user["email"],
        role=role["name"] if role else "user",
        tenant_id=user["tenant_id"],
        role_id=user.get("role_id"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        phone_number=user.get("phone_number"),
        guardian=user.get("guardian"),
        guardian_number=user.get("guardian_number"),
        city=user.get("city"),
        state=user.get("state"),
        country=user.get("country"),
        address_line1=user.get("address_line1"),
        address_line2=user.get("address_line2"),
        pincode=user.get("pincode"),
        aadhar_card_number=user.get("aadhar_card_number"),
        bank_name=user.get("bank_name"),
        account_number=user.get("account_number"),
        ifsc_code=user.get("ifsc_code"),
        profile_pic_url=user.get("profile_pic_url"),
        is_active=user.get("is_active"),
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at")
    )

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
        role_id=user.get("role_id"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        phone_number=user.get("phone_number"),
        guardian=user.get("guardian"),
        guardian_number=user.get("guardian_number"),
        city=user.get("city"),
        state=user.get("state"),
        country=user.get("country"),
        address_line1=user.get("address_line1"),
        address_line2=user.get("address_line2"),
        pincode=user.get("pincode"),
        aadhar_card_number=user.get("aadhar_card_number"),
        bank_name=user.get("bank_name"),
        account_number=user.get("account_number"),
        ifsc_code=user.get("ifsc_code"),
        profile_pic_url=user.get("profile_pic_url"),
        is_active=user.get("is_active"),
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at")
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

@router.put("/{user_id}/profile", response_model=UserWithDetails)
async def update_user_profile(
    user_id: str, 
    profile_data: UserProfileUpdate = Depends(),
    profile_pic: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    user = await users_repo.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if the user belongs to the current user's tenant
    if user["tenant_id"] != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Not authorized to update this user")
    
    update_data = profile_data.dict(exclude_unset=True)
    
    # Handle profile picture upload if provided
    if profile_pic:
        bucket_name = f"AWS_S3_BUCKET_{user['tenant_id']}"
        file_content = await profile_pic.read()
        file_extension = profile_pic.filename.split('.')[-1]
        file_key = f"profile_pics/{user_id}.{file_extension}"
        
        profile_pic_url = await upload_file_to_s3(
            bucket_name=bucket_name,
            file_key=file_key,
            file_content=io.BytesIO(file_content),
            content_type=profile_pic.content_type
        )
        
        update_data["profile_pic_url"] = profile_pic_url
    
    update_data["updated_at"] = datetime.utcnow()
    
    # Update user in database
    await users_repo.update_one({"_id": user_id}, update_data)
    
    # Get updated user
    updated_user = await users_repo.find_one({"_id": user_id})
    role = await roles_repo.find_one({"_id": updated_user["role_id"]}) if updated_user.get("role_id") else None
    
    return UserWithDetails(
        _id=updated_user["_id"],
        username=updated_user["username"],
        email=updated_user["email"],
        role=role["name"] if role else "user",
        tenant_id=updated_user["tenant_id"],
        role_id=updated_user.get("role_id"),
        first_name=updated_user.get("first_name"),
        last_name=updated_user.get("last_name"),
        phone_number=updated_user.get("phone_number"),
        guardian=updated_user.get("guardian"),
        guardian_number=updated_user.get("guardian_number"),
        city=updated_user.get("city"),
        state=updated_user.get("state"),
        country=updated_user.get("country"),
        address_line1=updated_user.get("address_line1"),
        address_line2=updated_user.get("address_line2"),
        pincode=updated_user.get("pincode"),
        aadhar_card_number=updated_user.get("aadhar_card_number"),
        bank_name=updated_user.get("bank_name"),
        account_number=updated_user.get("account_number"),
        ifsc_code=updated_user.get("ifsc_code"),
        profile_pic_url=updated_user.get("profile_pic_url"),
        is_active=updated_user.get("is_active"),
        created_at=updated_user.get("created_at"),
        updated_at=updated_user.get("updated_at")
    )

@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    user = await users_repo.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await users_repo.delete_one({"_id": user_id})
    
    return {"detail": "User deleted successfully"}