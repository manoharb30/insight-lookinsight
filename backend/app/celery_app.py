"""Celery application configuration for background task processing."""

from celery import Celery
from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "sec_insights",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max (large companies have many filings)
    task_soft_time_limit=1740,  # 29 minutes soft limit

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_concurrency=4,  # 4 concurrent workers
)
