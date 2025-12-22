"""Celery tasks for background processing."""

import asyncio
from typing import Dict, Any
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.agents.orchestrator import AnalysisPipeline
from app.services.supabase_service import supabase_service
from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory job status store (shared with API routes via Redis in production)
# For now, we use Redis to store job status
import redis
from app.config import get_settings

settings = get_settings()
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get job status from Redis."""
    import json
    data = redis_client.get(f"job:{job_id}")
    if data:
        return json.loads(data)
    return {}


def set_job_status(job_id: str, status: Dict[str, Any], expire: int = 3600):
    """Set job status in Redis."""
    import json
    redis_client.setex(f"job:{job_id}", expire, json.dumps(status))


def update_job_status(job_id: str, updates: Dict[str, Any]):
    """Update specific fields in job status."""
    current = get_job_status(job_id)
    current.update(updates)
    set_job_status(job_id, current)


class AnalysisTask(Task):
    """Custom Celery task with cleanup on revocation."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        job_id = kwargs.get("job_id") or args[0] if args else None
        if job_id:
            update_job_status(job_id, {
                "status": "failed",
                "message": str(exc),
            })
        logger.error(f"Task {task_id} failed: {exc}")

    def on_revoke(self, task_id, args, kwargs, request=None):
        """Handle task revocation (cancellation)."""
        job_id = kwargs.get("job_id") or args[0] if args else None
        if job_id:
            update_job_status(job_id, {
                "status": "cancelled",
                "message": "Analysis was cancelled",
            })
        logger.info(f"Task {task_id} was revoked/cancelled")


@celery_app.task(bind=True, base=AnalysisTask, name="run_analysis")
def run_analysis_task(self, job_id: str, ticker: str) -> Dict[str, Any]:
    """
    Run the multi-agent analysis pipeline as a Celery task.

    This task can be revoked/cancelled, and will update job status in Redis.
    """
    try:
        # Initialize job status
        set_job_status(job_id, {
            "id": job_id,
            "ticker": ticker,
            "status": "processing",
            "current_stage": "initializing",
            "message": "Starting analysis...",
            "progress": 0,
            "signals_found": 0,
            "result": None,
            "task_id": self.request.id,
        })

        # Create a wrapper that updates Redis instead of in-memory dict
        class RedisJobStore:
            def __getitem__(self, key):
                return get_job_status(key)

            def __setitem__(self, key, value):
                set_job_status(key, value)

            def __contains__(self, key):
                return redis_client.exists(f"job:{key}")

            def get(self, key, default=None):
                result = get_job_status(key)
                return result if result else default

            def update_job(self, key, updates):
                update_job_status(key, updates)

        jobs_store = RedisJobStore()

        # Run the async pipeline in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            pipeline = AnalysisPipeline(job_id, jobs_store)
            result = loop.run_until_complete(pipeline.run(ticker))

            # Update final status
            update_job_status(job_id, {
                "status": "completed",
                "current_stage": "complete",
                "progress": 100,
                "result": result,
            })

            # Cache result in Supabase
            loop.run_until_complete(
                supabase_service.cache_analysis(
                    ticker=ticker,
                    cik=result.get("cik", ""),
                    company_name=result.get("company_name", ""),
                    result=result,
                )
            )

            return result

        except SoftTimeLimitExceeded:
            update_job_status(job_id, {
                "status": "failed",
                "message": "Analysis timed out after 9 minutes",
            })
            raise

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Analysis task failed for {ticker}: {e}")
        update_job_status(job_id, {
            "status": "failed",
            "message": str(e),
        })
        raise


def cancel_analysis_task(job_id: str) -> bool:
    """
    Cancel a running analysis task.

    Returns True if task was found and revoked, False otherwise.
    """
    job_status = get_job_status(job_id)
    task_id = job_status.get("task_id")

    if not task_id:
        logger.warning(f"No task_id found for job {job_id}")
        return False

    # Revoke the task (terminate=True will kill the worker process)
    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

    # Update job status
    update_job_status(job_id, {
        "status": "cancelled",
        "message": "Analysis was cancelled by user",
    })

    logger.info(f"Cancelled task {task_id} for job {job_id}")
    return True
