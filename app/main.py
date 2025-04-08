from fastapi import FastAPI
import app.models
from app.api.v1.endpoints import appmodule as app_endpoint, auth, user, events, tenant, tasks, maps, emails
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import List
from app.db.session import ensure_collections_exist
from fastapi.openapi.models import SecurityScheme

app = FastAPI(
    title="MathscareDashbaordBE",
    description="Backend Docs For The Dashboard",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://65.0.172.221","http://ec2-65-0-172-221.ap-south-1.compute.amazonaws.com","https://dashboard.gajendrapurohit.in"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Ensure collections exist during application startup
    await ensure_collections_exist()

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(tenant.router, prefix="/admin", tags=["Tenant Management"])
app.include_router(events.router, prefix="/events", tags=["Events"])
app.include_router(app_endpoint.router, prefix="/app", tags=["App"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
app.include_router(maps.router, prefix="/maps", tags=["Maps"])
app.include_router(emails.router, prefix="/emails", tags=["Emails"])

