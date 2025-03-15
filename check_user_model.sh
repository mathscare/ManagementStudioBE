#!/bin/bash

# Script to check the User model definition

echo "Checking User model definition..."

# Activate virtual environment
source venv/bin/activate

# Check the User model file
echo "User model file content:"
cat app/models/user.py

# Check the database schema
echo -e "\nCurrent database schema for users table:"
psql postgresql://masteradmin:fastapidb@fastapi-db.c9c8eg0agu7x.ap-south-1.rds.amazonaws.com:5432/fastapi_db -c "\d users"

# Check if there are any pending migrations
echo -e "\nChecking for pending migrations:"
alembic current
alembic heads

echo "Check completed!" 