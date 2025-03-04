from fastapi import FastAPI
from app.api.v1.endpoints import auth, user, events
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="MathscareDashbaordBE",
    description="Backend Docs For The Dashboard",
    version="1.0.0",
)

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin
    allow_credentials=True,  # Allows cookies and authentication headers
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers (Authorization, Content-Type, etc.)
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(events.router, prefix="/events", tags=["Events"])
