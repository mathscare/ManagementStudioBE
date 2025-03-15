#!/bin/bash

# Script to fix common Gunicorn issues

echo "Fixing Gunicorn configuration..."

# Activate virtual environment
source venv/bin/activate

# Install or upgrade required packages
pip install --upgrade gunicorn uvicorn fastapi

# Fix the models/__init__.py file
cat > app/models/__init__.py << 'EOF'
# Import models in the correct order to avoid circular dependencies
from app.models.tenant import Tenant, Role, Permission
from app.models.user import User
from app.models.app import File, Tag
from app.models.event import Event
from app.models.task import Task, TaskStep, SubTask, TaskStatus, RecurrenceType
EOF

# Fix the main.py file
cat > app/main.py << 'EOF'
from fastapi import FastAPI
# Import models to ensure they are loaded before creating the app
import app.models
from app.api.v1.endpoints import appmodule as app_endpoint, auth, user, events, tenant, tasks
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
app.include_router(tenant.router, prefix="/admin", tags=["Tenant Management"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
EOF

# Create a test script to verify the application loads correctly
cat > test_app.py << 'EOF'
#!/usr/bin/env python
"""
Test script to verify the application loads correctly.
"""
import sys

try:
    print("Importing app.main...")
    import app.main
    print("Import successful!")
    print("Application loaded correctly.")
    sys.exit(0)
except Exception as e:
    print(f"Error importing app.main: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

# Make the test script executable
chmod +x test_app.py

# Run the test script
echo "Testing if the application loads correctly..."
python test_app.py

# If the test was successful, restart Gunicorn
if [ $? -eq 0 ]; then
    echo "Application loads correctly. Restarting Gunicorn..."
    sudo systemctl restart gunicorn
    echo "Gunicorn restarted."
else
    echo "Application failed to load. Please check the error message above."
fi

echo "Fix completed!" 