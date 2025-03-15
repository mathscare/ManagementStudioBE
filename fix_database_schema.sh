#!/bin/bash

# Script to fix the database schema mismatch

echo "Fixing database schema mismatch..."

# Activate virtual environment
source venv/bin/activate

# Check the current database schema
echo "Current database schema for users table:"
psql postgresql://masteradmin:fastapidb@fastapi-db.c9c8eg0agu7x.ap-south-1.rds.amazonaws.com:5432/fastapi_db -c "\d users"

# Create a new Alembic migration to add the missing columns
echo -e "\nCreating a new Alembic migration..."
alembic revision --autogenerate -m "Add missing columns to users table"

# Apply the migration
echo -e "\nApplying the migration..."
alembic upgrade head

# Check the updated database schema
echo -e "\nUpdated database schema for users table:"
psql postgresql://masteradmin:fastapidb@fastapi-db.c9c8eg0agu7x.ap-south-1.rds.amazonaws.com:5432/fastapi_db -c "\d users"

# Restart Gunicorn
echo -e "\nRestarting Gunicorn..."
sudo systemctl restart gunicorn

echo "Fix completed!" 