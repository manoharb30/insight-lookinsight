"""Celery tasks for background processing."""

import asyncio
from typing import Dict, Any
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.agents.orchestrator import AnalysisPipeline
from app.services.supabase_service import supabase_service
from app.services.neo4j_service import neo4j_service
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


# ==================== Running Jobs Tracking ====================
# Track which job is currently running for each ticker to prevent duplicates

def get_running_job_for_ticker(ticker: str) -> str | None:
    """Get the job ID of any currently running job for this ticker."""
    job_id = redis_client.get(f"running:{ticker.upper()}")
    if job_id:
        # Verify the job is still actually running
        status = get_job_status(job_id)
        if status.get("status") in ["pending", "processing"]:
            return job_id
        # Job finished/failed/cancelled, clean up stale reference
        clear_running_job_for_ticker(ticker)
    return None


def set_running_job_for_ticker(ticker: str, job_id: str, expire: int = 1800):
    """Mark a job as the running job for this ticker (30 min expiry as safety)."""
    redis_client.setex(f"running:{ticker.upper()}", expire, job_id)


def clear_running_job_for_ticker(ticker: str):
    """Clear the running job tracking for a ticker."""
    redis_client.delete(f"running:{ticker.upper()}")


class AnalysisTask(Task):
    """Custom Celery task with cleanup on revocation."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        job_id = kwargs.get("job_id") or args[0] if args else None
        ticker = kwargs.get("ticker") or (args[1] if len(args) > 1 else None)
        if job_id:
            update_job_status(job_id, {
                "status": "failed",
                "message": str(exc),
            })
        if ticker:
            clear_running_job_for_ticker(ticker)
        logger.error(f"Task {task_id} failed: {exc}")

    def on_revoke(self, task_id, args, kwargs, request=None):
        """Handle task revocation (cancellation)."""
        job_id = kwargs.get("job_id") or args[0] if args else None
        ticker = kwargs.get("ticker") or (args[1] if len(args) > 1 else None)
        if job_id:
            update_job_status(job_id, {
                "status": "cancelled",
                "message": "Analysis was cancelled",
            })
        if ticker:
            clear_running_job_for_ticker(ticker)
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
        class JobStatusWrapper(dict):
            """Dict wrapper that syncs updates to Redis."""
            def __init__(self, job_id, data):
                super().__init__(data)
                self._job_id = job_id

            def update(self, other):
                super().update(other)
                # Sync to Redis
                set_job_status(self._job_id, dict(self))

        class RedisJobStore:
            def __getitem__(self, key):
                data = get_job_status(key)
                return JobStatusWrapper(key, data)

            def __setitem__(self, key, value):
                set_job_status(key, value)

            def __contains__(self, key):
                return redis_client.exists(f"job:{key}")

            def get(self, key, default=None):
                if redis_client.exists(f"job:{key}"):
                    return JobStatusWrapper(key, get_job_status(key))
                return default

            def update_job(self, key, updates):
                update_job_status(key, updates)

        jobs_store = RedisJobStore()

        # Run the async pipeline in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Connect to Neo4j if not already connected (Celery workers are separate processes)
            if not neo4j_service._initialized:
                try:
                    loop.run_until_complete(neo4j_service.connect())
                    logger.info("Connected to Neo4j in Celery worker")
                except Exception as e:
                    logger.warning(f"Could not connect to Neo4j: {e} - continuing without graph features")

            pipeline = AnalysisPipeline(job_id, jobs_store)
            result = loop.run_until_complete(pipeline.run(ticker))

            # Update final status
            update_job_status(job_id, {
                "status": "completed",
                "current_stage": "complete",
                "progress": 100,
                "result": result,
            })

            # Clear running job tracking
            clear_running_job_for_ticker(ticker)

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
                "message": "Analysis timed out after 29 minutes",
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
        clear_running_job_for_ticker(ticker)
        raise


def cancel_analysis_task(job_id: str) -> bool:
    """
    Cancel a running analysis task.

    Returns True if task was found and revoked, False otherwise.
    """
    job_status = get_job_status(job_id)
    task_id = job_status.get("task_id")
    ticker = job_status.get("ticker")

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

    # Clear running job tracking
    if ticker:
        clear_running_job_for_ticker(ticker)

    logger.info(f"Cancelled task {task_id} for job {job_id}")
    return True
