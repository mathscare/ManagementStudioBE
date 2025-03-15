#!/usr/bin/env python
"""
Celery beat startup script.
Run this script to start the Celery beat scheduler:
    python celery_beat.py
"""
import os
from app.celery_worker.celery_app import celery_app

if __name__ == "__main__":
    # This will start the Celery beat scheduler
    celery_app.start(["beat", "--loglevel=info"]) 