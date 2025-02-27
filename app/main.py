from fastapi import FastAPI
from app.api.v1.endpoints import auth, user

app = FastAPI()

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
