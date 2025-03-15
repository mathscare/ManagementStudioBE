#!/usr/bin/env python
"""
Celery worker startup script.
Run this script to start the Celery worker:
    python celery_worker.py
"""
import os
from app.celery_worker.celery_app import celery_app

if __name__ == "__main__":
    # This will start the Celery worker
    celery_app.worker_main(["worker", "--loglevel=info"]) 