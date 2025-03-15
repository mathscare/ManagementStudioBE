from celery import Celery
import os

# Create Celery app
celery_app = Celery(
    "worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

# Configure task routes
celery_app.conf.task_routes = {
    "app.celery_worker.tasks.*": "main-queue"
}

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    "process-recurring-tasks": {
        "task": "app.celery_worker.tasks.recurring_tasks.process_recurring_tasks",
        "schedule": 60.0 * 60,  # Run every hour
    },
} 