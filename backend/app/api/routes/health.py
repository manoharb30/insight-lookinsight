from fastapi import APIRouter
from app.services.neo4j_service import neo4j_service
from app.services.supabase_service import supabase_service

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint for Railway deployment."""
    neo4j_healthy = await neo4j_service.health_check()
    supabase_healthy = await supabase_service.health_check()

    return {
        "status": "healthy" if neo4j_healthy and supabase_healthy else "degraded",
        "services": {
            "neo4j": "connected" if neo4j_healthy else "disconnected",
            "supabase": "connected" if supabase_healthy else "disconnected",
        },
    }


@router.get("/health/live")
async def liveness():
    """Simple liveness probe."""
    return {"status": "alive"}
