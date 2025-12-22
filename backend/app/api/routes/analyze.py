import uuid
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from typing import Optional
import json

from app.agents.orchestrator import AnalysisPipeline
from app.services.supabase_service import supabase_service

router = APIRouter()

# In-memory job store (use Redis in production)
jobs: dict = {}


class AnalyzeRequest(BaseModel):
    ticker: str


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str
    cached: bool = False


@router.post("/analyze", response_model=AnalyzeResponse)
async def start_analysis(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
):
    """Start a new analysis job for the given ticker."""
    ticker = request.ticker.upper().strip()

    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    # Check cache first
    cached = await supabase_service.get_cached_analysis(ticker)
    if cached and cached.get("status") == "completed":
        return AnalyzeResponse(
            job_id=cached["id"],
            status="completed",
            cached=True,
        )

    # Create new job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "ticker": ticker,
        "status": "pending",
        "current_stage": "initializing",
        "message": "Starting analysis...",
        "progress": 0,
        "signals_found": 0,
        "result": None,
    }

    # Start pipeline in background
    background_tasks.add_task(run_analysis_pipeline, job_id, ticker)

    return AnalyzeResponse(job_id=job_id, status="processing")


async def run_analysis_pipeline(job_id: str, ticker: str):
    """Run the multi-agent analysis pipeline."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["current_stage"] = "fetching"
        jobs[job_id]["message"] = "Fetching SEC filings..."

        pipeline = AnalysisPipeline(job_id, jobs)
        result = await pipeline.run(ticker)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["current_stage"] = "complete"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["result"] = result

        # Cache result in Supabase
        await supabase_service.cache_analysis(
            ticker=ticker,
            cik=result.get("cik", ""),
            company_name=result.get("company_name", ""),
            result=result,
        )

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = str(e)
        print(f"Analysis failed for {ticker}: {e}")


@router.get("/analyze/{job_id}")
async def get_analysis_status(job_id: str):
    """Get the status of an analysis job."""
    if job_id not in jobs:
        # Check Supabase for cached result
        cached = await supabase_service.get_analysis_by_id(job_id)
        if cached:
            return cached
        raise HTTPException(status_code=404, detail="Job not found")

    return jobs[job_id]


@router.get("/stream/{job_id}")
async def stream_analysis(job_id: str):
    """SSE stream for real-time analysis updates."""

    async def event_generator():
        while True:
            if job_id not in jobs:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Job not found"}),
                }
                break

            status = jobs[job_id]

            yield {
                "event": "update",
                "data": json.dumps(
                    {
                        "stage": status["current_stage"],
                        "message": status["message"],
                        "progress": status["progress"],
                        "signals_found": status["signals_found"],
                    }
                ),
            }

            if status["status"] in ["completed", "failed"]:
                yield {
                    "event": "complete",
                    "data": json.dumps(status.get("result") or {"error": status.get("message")}),
                }
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
