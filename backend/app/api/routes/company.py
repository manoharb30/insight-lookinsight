from fastapi import APIRouter, HTTPException
from app.services.supabase_service import supabase_service
from app.services.neo4j_service import neo4j_service

router = APIRouter()


@router.get("/company/{ticker}")
async def get_company(ticker: str):
    """Get cached analysis for a company if it exists."""
    ticker = ticker.upper().strip()

    cached = await supabase_service.get_cached_analysis(ticker)
    if not cached:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker")

    return cached


@router.get("/similar/{ticker}")
async def get_similar_companies(ticker: str):
    """Get companies with similar risk profiles."""
    ticker = ticker.upper().strip()

    similar = await neo4j_service.find_similar_companies(ticker)
    return {"ticker": ticker, "similar_companies": similar}


@router.get("/patterns/{ticker}")
async def get_bankruptcy_patterns(ticker: str):
    """Match company's signals to known bankruptcy patterns."""
    ticker = ticker.upper().strip()

    patterns = await neo4j_service.match_bankruptcy_patterns(ticker)
    return {"ticker": ticker, "pattern_matches": patterns}
