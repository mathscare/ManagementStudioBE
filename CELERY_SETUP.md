# Celery Setup Instructions

This document provides instructions for setting up Celery for task scheduling in the Management Studio Backend.

## Prerequisites

- Redis server installed
- Python 3.8+
- Virtual environment activated

## Installation

1. Install required packages:

```bash
pip install celery redis
```

2. Ensure Redis is running:

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

## Configuration

The Celery configuration is located in `app/celery_worker/celery_app.py`. This file defines:

- The Celery application
- Task routing
- Periodic task schedules

## Running Celery

### Development Environment

To run Celery in a development environment:

1. Start the Celery worker:

```bash
python celery_worker.py
```

2. Start the Celery beat scheduler:

```bash
python celery_beat.py
```

### Production Environment (EC2)

For production deployment on EC2:

1. Copy the systemd service files to the system directory:

```bash
sudo cp celery.service /etc/systemd/system/
sudo cp celerybeat.service /etc/systemd/system/
```

2. Reload systemd:

```bash
sudo systemctl daemon-reload
```

3. Enable and start the services:

```bash
sudo systemctl enable celery.service
sudo systemctl enable celerybeat.service
sudo systemctl start celery.service
sudo systemctl start celerybeat.service
```

4. Check the status:

```bash
sudo systemctl status celery.service
sudo systemctl status celerybeat.service
```

## Automated Setup

You can use the provided setup script to automate the installation and configuration:

```bash
chmod +x setup_celery.sh
./setup_celery.sh
```

## Recurring Tasks

The system uses Celery to handle recurring tasks. The logic for processing recurring tasks is defined in `app/celery_worker/tasks/recurring_tasks.py`.

The scheduler checks hourly for tasks that need to be recreated based on their recurrence settings (daily, weekly, monthly, yearly).

## Logs

To view Celery logs:

```bash
# Worker logs
sudo journalctl -u celery.service

# Beat logs
sudo journalctl -u celerybeat.service
``` 