from supabase import create_client, Client
from typing import Dict, Any, Optional, List
import json
from datetime import datetime, timedelta

from app.config import get_settings

settings = get_settings()


class SupabaseService:
    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )

    async def health_check(self) -> bool:
        """Check if Supabase connection is healthy."""
        try:
            # Simple query to check connection
            self.client.table("analyses").select("id").limit(1).execute()
            return True
        except Exception:
            return False

    async def get_cached_analysis(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis for a ticker if it exists and is not expired."""
        try:
            result = (
                self.client.table("analyses")
                .select("*")
                .eq("ticker", ticker)
                .gte("expires_at", datetime.utcnow().isoformat())
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
            return None
        except Exception:
            return None

    async def get_analysis_by_id(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis by ID."""
        try:
            result = (
                self.client.table("analyses")
                .select("*")
                .eq("id", analysis_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
            return None
        except Exception:
            return None

    async def cache_analysis(self, ticker: str, result: Dict[str, Any]) -> str:
        """Cache an analysis result."""
        data = {
            "ticker": ticker,
            "cik": result.get("cik", ""),
            "company_name": result.get("company_name", ""),
            "status": "completed",
            "risk_score": result.get("risk_score", 0),
            "signal_count": len(result.get("signals", [])),
            "result": json.dumps(result),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        response = self.client.table("analyses").insert(data).execute()
        return response.data[0]["id"]

    async def store_filing_chunks(
        self,
        ticker: str,
        filing_accession: str,
        filing_type: str,
        chunks: List[Dict[str, Any]],
    ):
        """Store filing chunks with embeddings for vector search."""
        data = [
            {
                "ticker": ticker,
                "filing_accession": filing_accession,
                "filing_type": filing_type,
                "item_number": chunk.get("item_number", ""),
                "content": chunk["content"],
                "embedding": chunk["embedding"],
            }
            for chunk in chunks
        ]

        self.client.table("filing_chunks").insert(data).execute()

    async def search_similar_chunks(
        self,
        embedding: List[float],
        ticker: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks using vector similarity."""
        # Use Supabase's vector similarity search
        params = {
            "query_embedding": embedding,
            "match_count": limit,
        }
        if ticker:
            params["filter"] = {"ticker": ticker}

        result = self.client.rpc("match_filing_chunks", params).execute()
        return result.data

    async def update_analysis_status(
        self,
        analysis_id: str,
        status: str,
        message: Optional[str] = None,
    ):
        """Update the status of an analysis."""
        data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
        if message:
            data["message"] = message

        self.client.table("analyses").update(data).eq("id", analysis_id).execute()


# Singleton instance
supabase_service = SupabaseService()
