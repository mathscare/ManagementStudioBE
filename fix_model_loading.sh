#!/bin/bash

# Script to fix the model loading issue on the EC2 instance

echo "Fixing model loading issue..."

# Activate virtual environment
source venv/bin/activate

# Update the models/__init__.py file
cat > app/models/__init__.py << 'EOF'
# Import models in the correct order to avoid circular dependencies
from app.models.tenant import Tenant, Role, Permission
from app.models.user import User
from app.models.app import File, Tag
from app.models.event import Event
from app.models.task import Task, TaskStep, Subtask, TaskStatus, RecurrenceType

# This ensures that all models are properly loaded and relationships are established
# before SQLAlchemy tries to create the tables
EOF

# Update the main.py file
sed -i '1s/^/from fastapi import FastAPI\n# Import models to ensure they are loaded before creating the app\nimport app.models\n/' app/main.py
sed -i '1d' app/main.py

# Create the migration script
cat > run_migration.py << 'EOF'
#!/usr/bin/env python
"""
Script to run Alembic migrations.
This ensures models are loaded in the correct order before migrations are run.
"""
import os
import sys
import subprocess

# Import models to ensure they are loaded in the correct order
import app.models

def run_migration():
    """Run Alembic migration"""
    print("Running Alembic migration...")
    
    # Run alembic upgrade
    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        print("Migration completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
EOF

# Make the script executable
chmod +x run_migration.py

# Run the migration
python run_migration.py

# Restart the application
sudo systemctl restart gunicorn

echo "Fix completed!" 