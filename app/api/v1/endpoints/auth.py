from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import create_access_token, pwd_context
from app.db.session import get_db
from app.models.user import User as DBUser
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.core.config import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError



router = APIRouter()
ACCESS_TOKEN_EXPIRE_MINUTES = 30

@router.post("/signup/", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    existing_email = db.query(DBUser).filter(DBUser.email == user.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    if user.role:
        raise HTTPException(status_code=400, detail=user.role)
    hashed_password = pwd_context.hash(user.password)
    new_user = DBUser(username=user.username, email=user.email, hashed_password=hashed_password,role = user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login/", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh/")
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = db.query(DBUser).filter(DBUser.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        # Create a new access token
        new_access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return {"access_token": new_access_token, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")