#!/bin/bash

# Install Redis if not already installed
sudo apt-get update
sudo apt-get install -y redis-server

# Ensure Redis is running
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Install Celery and Redis Python packages
pip install celery redis

# Copy systemd service files
sudo cp celery.service /etc/systemd/system/
sudo cp celerybeat.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start Celery services
sudo systemctl enable celery.service
sudo systemctl enable celerybeat.service
sudo systemctl start celery.service
sudo systemctl start celerybeat.service

# Check status
echo "Celery worker status:"
sudo systemctl status celery.service
echo "Celery beat status:"
sudo systemctl status celerybeat.service

echo "Celery setup complete!" 