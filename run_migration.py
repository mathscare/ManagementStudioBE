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