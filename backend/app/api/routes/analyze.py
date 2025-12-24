"""Analysis API routes with Celery task queue and cancellation support."""

import uuid
import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from typing import Optional

from app.tasks import (
    run_analysis_task,
    cancel_analysis_task,
    get_job_status,
    set_job_status,
    get_running_job_for_ticker,
    set_running_job_for_ticker,
)
from app.services.supabase_service import supabase_service
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    ticker: str


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str
    cached: bool = False


class CancelResponse(BaseModel):
    job_id: str
    cancelled: bool
    message: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def start_analysis(request: AnalyzeRequest):
    """Start a new analysis job for the given ticker."""
    ticker = request.ticker.upper().strip()

    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    # Check cache first (completed analysis in Supabase)
    cached = await supabase_service.get_cached_analysis(ticker)
    if cached and cached.get("status") == "completed":
        return AnalyzeResponse(
            job_id=cached["id"],
            status="completed",
            cached=True,
        )

    # Check if there's already a running job for this ticker
    existing_job_id = get_running_job_for_ticker(ticker)
    if existing_job_id:
        logger.info(f"Returning existing job {existing_job_id} for {ticker}")
        return AnalyzeResponse(
            job_id=existing_job_id,
            status="processing",
            cached=False,
        )

    # Create new job
    job_id = str(uuid.uuid4())

    # Initialize job status in Redis
    set_job_status(job_id, {
        "id": job_id,
        "ticker": ticker,
        "status": "pending",
        "current_stage": "initializing",
        "message": "Starting analysis...",
        "progress": 0,
        "signals_found": 0,
        "result": None,
    })

    # Mark this as the running job for this ticker
    set_running_job_for_ticker(ticker, job_id)

    # Start Celery task
    task = run_analysis_task.delay(job_id=job_id, ticker=ticker)

    # Store task ID for cancellation
    set_job_status(job_id, {
        "id": job_id,
        "ticker": ticker,
        "status": "processing",
        "current_stage": "initializing",
        "message": "Starting analysis...",
        "progress": 0,
        "signals_found": 0,
        "result": None,
        "task_id": task.id,
    })

    logger.info(f"Started analysis job {job_id} (task: {task.id}) for {ticker}")

    return AnalyzeResponse(job_id=job_id, status="processing")


@router.post("/analyze/{job_id}/cancel", response_model=CancelResponse)
async def cancel_analysis(job_id: str):
    """Cancel a running analysis job."""
    job_status = get_job_status(job_id)

    if not job_status:
        raise HTTPException(status_code=404, detail="Job not found")

    current_status = job_status.get("status")

    # Can only cancel pending or processing jobs
    if current_status in ["completed", "failed", "cancelled"]:
        return CancelResponse(
            job_id=job_id,
            cancelled=False,
            message=f"Job already {current_status}, cannot cancel",
        )

    # Cancel the Celery task
    success = cancel_analysis_task(job_id)

    if success:
        return CancelResponse(
            job_id=job_id,
            cancelled=True,
            message="Analysis cancelled successfully",
        )
    else:
        return CancelResponse(
            job_id=job_id,
            cancelled=False,
            message="Could not cancel task (may have already completed)",
        )


@router.get("/analyze/{job_id}")
async def get_analysis_status(job_id: str):
    """Get the status of an analysis job."""
    # Check Redis first
    job_status = get_job_status(job_id)
    if job_status:
        return job_status

    # Check Supabase for cached result
    cached = await supabase_service.get_analysis_by_id(job_id)
    if cached:
        return cached

    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/stream/{job_id}")
async def stream_analysis(job_id: str, request: Request):
    """
    SSE stream for real-time analysis updates.

    Automatically cancels the task if client disconnects.
    """

    async def event_generator():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected for job {job_id}, cancelling task")
                    cancel_analysis_task(job_id)
                    break

                status = get_job_status(job_id)

                if not status:
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Job not found"}),
                    }
                    break

                yield {
                    "event": "update",
                    "data": json.dumps(
                        {
                            "stage": status.get("current_stage", "unknown"),
                            "message": status.get("message", ""),
                            "progress": status.get("progress", 0),
                            "signals_found": status.get("signals_found", 0),
                        }
                    ),
                }

                job_status = status.get("status")
                if job_status in ["completed", "failed", "cancelled"]:
                    if job_status == "completed":
                        yield {
                            "event": "complete",
                            "data": json.dumps(status.get("result") or {}),
                        }
                    elif job_status == "cancelled":
                        yield {
                            "event": "cancelled",
                            "data": json.dumps({"message": "Analysis was cancelled"}),
                        }
                    else:
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": status.get("message", "Analysis failed")}),
                        }
                    break

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            # Client disconnected, cancel the task
            logger.info(f"SSE cancelled for job {job_id}, cancelling task")
            cancel_analysis_task(job_id)
            raise

    return EventSourceResponse(event_generator())
