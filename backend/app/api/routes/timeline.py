"""Timeline API endpoints - Facts only, no scoring.

Shows signal timeline with evidence and filing context.
User interprets the data themselves.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.repositories.neo4j_repository import neo4j_repository
from app.services.neo4j_service import neo4j_service
from app.models.timeline_models import (
    CompanyTimeline,
    CompanyInfo,
    SignalDetail,
    FilingDetail,
    FilingInfo,
    SimilarCase,
    GoingConcernHistory,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/timeline", tags=["timeline"])


async def ensure_neo4j_connected():
    """Ensure Neo4j is connected, reconnect if needed."""
    if not await neo4j_service.health_check():
        try:
            await neo4j_service.connect()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Neo4j unavailable: {e}")


@router.get("/{ticker}", response_model=CompanyTimeline)
async def get_company_timeline(ticker: str):
    """
    Get complete signal timeline for a company.

    Returns:
    - Company info (status, going concern status, days since last signal)
    - All detected signals with evidence and filing links
    - Recent filings (last 12 months)

    NO risk scores or predictions - facts only.
    """
    await ensure_neo4j_connected()
    ticker = ticker.upper()

    timeline = await neo4j_repository.get_company_timeline(ticker)

    if not timeline:
        raise HTTPException(status_code=404, detail=f"Company {ticker} not found")

    return timeline


@router.get("/{ticker}/going-concern", response_model=GoingConcernHistory)
async def get_going_concern_history(ticker: str):
    """
    Track going concern status across annual 10-K filings.

    Shows year-by-year whether going concern warning was present,
    highlighting when it was added or removed.
    """
    await ensure_neo4j_connected()
    ticker = ticker.upper()

    history = await neo4j_repository.get_going_concern_history(ticker)
    return history


@router.get("/{ticker}/filings", response_model=List[FilingDetail])
async def get_recent_filings(
    ticker: str,
    months: int = Query(default=12, ge=1, le=36),
    category: Optional[str] = Query(default=None, regex="^(DISTRESS|ROUTINE|CORPORATE_ACTION)$"),
):
    """
    Get recent filings for a company.

    Categories:
    - DISTRESS: Contains distress signals (going concern, layoffs, etc.)
    - ROUTINE: Normal business filings (earnings, appointments)
    - CORPORATE_ACTION: Stock splits, M&A, financing
    """
    await ensure_neo4j_connected()
    ticker = ticker.upper()

    filings = await neo4j_repository.get_recent_filings(
        ticker,
        months=months,
        category=category,
    )
    return filings


@router.get("/{ticker}/similar", response_model=List[SimilarCase])
async def get_similar_cases(
    ticker: str,
    min_overlap: int = Query(default=2, ge=1, le=10),
):
    """
    Find historical cases with similar signal patterns.

    Returns companies that had the same types of signals,
    with their eventual outcome (BANKRUPT or still ACTIVE).

    This is NOT a prediction - just historical comparison.
    User interprets what this means for their analysis.
    """
    await ensure_neo4j_connected()
    ticker = ticker.upper()

    cases = await neo4j_repository.get_similar_cases(ticker, min_overlap)
    return cases


@router.get("/overview/by-recency")
async def get_companies_by_signal_recency():
    """
    Group all tracked companies by how recent their last signal was.

    Buckets:
    - last_30_days: Very recent activity
    - last_90_days: Recent activity
    - last_180_days: Moderate activity
    - over_180_days: Quiet (could be recovering or out of distress)
    """
    await ensure_neo4j_connected()

    return await neo4j_repository.get_companies_by_signal_recency()


@router.post("/{ticker}/sync")
async def sync_company_to_neo4j(ticker: str):
    """
    Sync company signals from analysis pipeline to Neo4j.

    Runs the full analysis and stores results in Neo4j graph.
    """
    await ensure_neo4j_connected()
    ticker = ticker.upper()

    # Run analysis pipeline
    from app.agents.orchestrator import AnalysisPipeline
    from app.services.neo4j_sync_service import neo4j_sync_service

    class SimpleJobStore(dict):
        def update_job(self, key, updates):
            if key in self:
                self[key].update(updates)

    jobs = SimpleJobStore()
    job_id = f"sync-{ticker.lower()}"
    jobs[job_id] = {"id": job_id, "ticker": ticker, "status": "processing"}

    try:
        pipeline = AnalysisPipeline(job_id, jobs)
        result = await pipeline.run(ticker)

        # Sync to Neo4j using facts-only sync service
        sync_result = await neo4j_sync_service.sync_from_analysis(
            ticker=ticker,
            company_data={
                "cik": result.get("cik", ""),
                "name": result.get("company_name", ticker),
                "status": "ACTIVE",
            },
            signals=result.get("signals", []),
        )

        return {
            "status": "success",
            "ticker": ticker,
            "signals_synced": sync_result.get("signals_created", 0),
            "going_concern_status": sync_result.get("going_concern_status"),
            "chain_relationships": sync_result.get("chain_relationships", 0),
        }

    except Exception as e:
        logger.error(f"Error syncing {ticker} to Neo4j: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ticker}/sync-from-cache")
async def sync_from_supabase_cache(ticker: str):
    """
    Sync company from existing Supabase cache to Neo4j.

    Faster than full sync - uses cached analysis results.
    """
    await ensure_neo4j_connected()
    ticker = ticker.upper()

    from app.services.neo4j_sync_service import neo4j_sync_service

    result = await neo4j_sync_service.sync_from_supabase(ticker)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
