from fastapi import FastAPI
from app.api.v1.endpoints import appmodule as app_endpoint, auth, user, events
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="MathscareDashbaordBE",
    description="Backend Docs For The Dashboard",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(events.router, prefix="/events", tags=["Events"])
app.include_router(app_endpoint.router, prefix="/app", tags=["App"])

