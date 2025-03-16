from fastapi import FastAPI
# Import models to ensure they are loaded before creating the app
import app.models
from app.api.v1.endpoints import appmodule as app_endpoint, auth, user, events, tenant, tasks
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import List

app = FastAPI(
    title="MathscareDashbaordBE",
    description="Backend Docs For The Dashboard",
    version="1.0.0",
)

# Get allowed origins from environment variable or use default
# Format: "http://domain1.com,https://domain2.com,http://localhost:5173"
origins_str = os.getenv("ALLOWED_ORIGINS", "*")
origins: List[str] = [origins_str] if origins_str == "*" else origins_str.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(events.router, prefix="/events", tags=["Events"])
app.include_router(app_endpoint.router, prefix="/app", tags=["App"])
app.include_router(tenant.router, prefix="/admin", tags=["Tenant Management"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])

