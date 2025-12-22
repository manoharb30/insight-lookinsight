from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.api.routes import analyze, company, health
from app.services.neo4j_service import neo4j_service
from app.services.supabase_service import supabase_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up Insight Lookinsight API...")
    await neo4j_service.connect()
    print("Connected to Neo4j")
    yield
    # Shutdown
    print("Shutting down...")
    await neo4j_service.close()


app = FastAPI(
    title="Insight Lookinsight API",
    description="Multi-agent SEC filing analysis for bankruptcy risk detection",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, tags=["Health"])
app.include_router(analyze.router, prefix=settings.api_v1_prefix, tags=["Analysis"])
app.include_router(company.router, prefix=settings.api_v1_prefix, tags=["Company"])


@app.get("/")
async def root():
    return {
        "name": "Insight Lookinsight API",
        "version": "0.1.0",
        "description": "Multi-agent SEC filing analysis platform",
    }
