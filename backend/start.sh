#!/bin/bash

# Start Celery worker in background
celery -A app.celery_app worker --loglevel=info --concurrency=2 &

# Start FastAPI server (foreground)
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
