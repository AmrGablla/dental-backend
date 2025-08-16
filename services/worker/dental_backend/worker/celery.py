"""Celery configuration for the dental backend worker service."""

from celery import Celery
from dental_backend_common.config import get_settings

# Get settings
settings = get_settings()

# Create Celery app
celery = Celery(
    "dental_backend",
    broker=settings.worker.broker_url,
    backend=settings.worker.result_backend,
    include=["dental_backend.worker.tasks"],
)

# Configure Celery
celery.conf.update(
    task_serializer=settings.worker.task_serializer,
    result_serializer=settings.worker.result_serializer,
    accept_content=settings.worker.accept_content,
    timezone=settings.worker.timezone,
    enable_utc=settings.worker.enable_utc,
    task_track_started=settings.worker.task_track_started,
    task_time_limit=settings.worker.task_time_limit,
    task_soft_time_limit=settings.worker.task_soft_time_limit,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=True,
)

# Optional: Configure result backend
if settings.worker.result_backend:
    celery.conf.result_backend = settings.worker.result_backend

if __name__ == "__main__":
    celery.start()
