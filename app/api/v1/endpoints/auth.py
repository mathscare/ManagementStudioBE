from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import create_access_token, pwd_context
from app.db.session import get_db
from app.models.user import User as DBUser
from app.models.tenant import Tenant, Role
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.core.config import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError

router = APIRouter()
ACCESS_TOKEN_EXPIRE_MINUTES = 30

@router.post("/signup/", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username already exists
    existing_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists
    existing_email = db.query(DBUser).filter(DBUser.email == user.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password
    hashed_password = pwd_context.hash(user.password)
    
    # Create or get tenant
    tenant_id = user.tenant_id
    if not tenant_id:
        # Create a new tenant based on organization name
        tenant = Tenant(name=user.organization_name, description=f"Tenant for {user.organization_name}")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        tenant_id = tenant.id
        
        # Create a default admin role for this tenant
        admin_role = Role(
            name="tenant_admin",
            description="Default administrator role for the tenant",
            tenant_id=tenant_id
        )
        db.add(admin_role)
        db.commit()
    
    # Create the user
    new_user = DBUser(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role,
        tenant_id=tenant_id
    )

    # If this is the first user for a new tenant, assign them the tenant_admin role
    if user.role == "tenant_admin":
        admin_role = db.query(Role).filter(
            Role.name == "tenant_admin",
            Role.tenant_id == tenant_id
        ).first()
        if admin_role:
            new_user.role_id = admin_role.id

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login/", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Create token data
    token_data = {
        "sub": user.username, 
        "tenant_id": user.tenant_id,
        "role": user.role
    }
    
    # Add role_id if it exists
    if user.role_id:
        token_data["role_id"] = user.role_id
    
    # Create access token
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Create refresh token
    refresh_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 336)  # 2 weeks
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "role": user.role, 
        "refresh_token": refresh_token
    }

@router.post("/refresh/")
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        tenant_id: int = payload.get("tenant_id")
        
        if username is None or tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = db.query(DBUser).filter(DBUser.username == username, DBUser.tenant_id == tenant_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        # Create token data
        token_data = {
            "sub": user.username, 
            "tenant_id": user.tenant_id,
            "role": user.role
        }
        
        # Add role_id if it exists
        if user.role_id:
            token_data["role_id"] = user.role_id
            
        # Create new access token
        new_access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return {
            "access_token": new_access_token, 
            "token_type": "bearer",
            "role": user.role,
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")