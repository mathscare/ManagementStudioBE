#!/bin/bash

# Script to check Gunicorn configuration and get the full error message

echo "Checking Gunicorn configuration..."

# Get the Gunicorn service file
echo "Gunicorn service file:"
sudo cat /etc/systemd/system/gunicorn.service

# Get the full error message
echo -e "\nFull error message from journal:"
sudo journalctl -u gunicorn -n 100 --no-pager

# Try to run the application directly to see the error
echo -e "\nTrying to run the application directly:"
cd /home/ubuntu/fastapi-backend
source venv/bin/activate
python -c "import app.main; print('Import successful')"

# Check the Python path
echo -e "\nPython path:"
python -c "import sys; print(sys.path)"

# Check if we can import the models
echo -e "\nTrying to import models:"
python -c "import app.models; print('Models imported successfully')"

echo "Check completed!" 