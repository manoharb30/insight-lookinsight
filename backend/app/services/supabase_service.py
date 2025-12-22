"""Supabase service for PostgreSQL + pgvector operations.

Stores: Users, Cached analyses, Filing chunks, Embeddings
"""

from supabase import create_client, Client
from typing import Dict, Any, Optional, List
import json
from datetime import datetime, timedelta

from app.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import DatabaseError

logger = get_logger(__name__)
settings = get_settings()


class SupabaseService:
    """
    Supabase service for PostgreSQL and pgvector operations.

    Responsible for:
    - User management (future)
    - Caching analysis results
    - Storing filing chunks with embeddings for vector search
    """

    def __init__(self):
        self._client: Optional[Client] = None
        self._initialized = False

    def connect(self) -> None:
        """Initialize Supabase client."""
        try:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_service_key,
            )
            self._initialized = True
            logger.info("Connected to Supabase successfully")
        except Exception as e:
            logger.error(f"Supabase connection error: {e}")
            raise DatabaseError("Supabase", str(e))

    @property
    def client(self) -> Client:
        """Get the Supabase client, connecting if necessary."""
        if not self._client:
            self.connect()
        return self._client

    async def health_check(self) -> bool:
        """Check if Supabase connection is healthy."""
        try:
            self.client.table("analyses").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.warning(f"Supabase health check failed: {e}")
            return False

    # ==================== Analysis Cache ====================

    async def get_cached_analysis(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis for a ticker if it exists and is not expired.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Cached analysis or None
        """
        try:
            result = (
                self.client.table("analyses")
                .select("*")
                .eq("ticker", ticker.upper())
                .gte("expires_at", datetime.utcnow().isoformat())
                .eq("status", "completed")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                analysis = result.data[0]
                # Parse JSON result if stored as string
                if isinstance(analysis.get("result"), str):
                    analysis["result"] = json.loads(analysis["result"])
                logger.info(f"Cache hit for {ticker}")
                return analysis
            return None
        except Exception as e:
            logger.error(f"Error getting cached analysis: {e}")
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
                analysis = result.data[0]
                if isinstance(analysis.get("result"), str):
                    analysis["result"] = json.loads(analysis["result"])
                return analysis
            return None
        except Exception as e:
            logger.error(f"Error getting analysis by ID: {e}")
            return None

    async def cache_analysis(
        self,
        ticker: str,
        cik: str,
        company_name: str,
        result: Dict[str, Any],
        ttl_days: int = 7,
    ) -> str:
        """
        Cache an analysis result.

        Args:
            ticker: Stock ticker
            cik: Company CIK
            company_name: Company name
            result: Analysis result dict
            ttl_days: Time to live in days

        Returns:
            Analysis ID
        """
        try:
            data = {
                "ticker": ticker.upper(),
                "cik": cik,
                "company_name": company_name,
                "status": "completed",
                "risk_score": result.get("risk_score", 0),
                "signal_count": result.get("signal_count", 0),
                "result": json.dumps(result),
                "expires_at": (datetime.utcnow() + timedelta(days=ttl_days)).isoformat(),
            }

            response = self.client.table("analyses").insert(data).execute()
            analysis_id = response.data[0]["id"]
            logger.info(f"Cached analysis for {ticker}: {analysis_id}")
            return analysis_id
        except Exception as e:
            logger.error(f"Error caching analysis: {e}")
            raise DatabaseError("Supabase", f"Failed to cache analysis: {e}")

    async def update_analysis_status(
        self,
        analysis_id: str,
        status: str,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update the status of an analysis."""
        try:
            data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
            }
            if message:
                data["message"] = message
            if result:
                data["result"] = json.dumps(result)
                data["risk_score"] = result.get("risk_score", 0)
                data["signal_count"] = result.get("signal_count", 0)

            self.client.table("analyses").update(data).eq("id", analysis_id).execute()
        except Exception as e:
            logger.error(f"Error updating analysis status: {e}")

    # ==================== Filing Chunks & Embeddings ====================

    async def store_filing_chunk(
        self,
        ticker: str,
        cik: str,
        accession_number: str,
        filing_type: str,
        item_number: str,
        content: str,
        embedding: List[float],
        chunk_index: int = 0,
    ) -> str:
        """
        Store a single filing chunk with its embedding.

        Args:
            ticker: Stock ticker
            cik: Company CIK
            accession_number: Filing accession number
            filing_type: Filing type (8-K, 10-K, etc.)
            item_number: Item number within filing
            content: Chunk text content
            embedding: Vector embedding (1536 dimensions)
            chunk_index: Index of chunk within item

        Returns:
            Chunk ID
        """
        try:
            data = {
                "ticker": ticker.upper(),
                "cik": cik,
                "accession_number": accession_number,
                "filing_type": filing_type,
                "item_number": item_number,
                "content": content,
                "embedding": embedding,
                "chunk_index": chunk_index,
            }

            response = self.client.table("filing_chunks").insert(data).execute()
            return response.data[0]["id"]
        except Exception as e:
            logger.error(f"Error storing filing chunk: {e}")
            raise DatabaseError("Supabase", f"Failed to store chunk: {e}")

    async def store_filing_chunks_batch(
        self,
        ticker: str,
        cik: str,
        accession_number: str,
        filing_type: str,
        chunks: List[Dict[str, Any]],
    ) -> int:
        """
        Store multiple filing chunks in batch.

        Args:
            ticker: Stock ticker
            cik: Company CIK
            accession_number: Filing accession number
            filing_type: Filing type
            chunks: List of chunk dicts with content, item_number, embedding

        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0

        try:
            data = [
                {
                    "ticker": ticker.upper(),
                    "cik": cik,
                    "accession_number": accession_number,
                    "filing_type": filing_type,
                    "item_number": chunk.get("item_number", ""),
                    "content": chunk["content"],
                    "embedding": chunk["embedding"],
                    "chunk_index": i,
                }
                for i, chunk in enumerate(chunks)
            ]

            self.client.table("filing_chunks").insert(data).execute()
            logger.info(f"Stored {len(chunks)} chunks for {accession_number}")
            return len(chunks)
        except Exception as e:
            logger.error(f"Error storing filing chunks batch: {e}")
            raise DatabaseError("Supabase", f"Failed to store chunks: {e}")

    async def search_similar_chunks(
        self,
        embedding: List[float],
        ticker: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using vector similarity.

        Args:
            embedding: Query embedding vector
            ticker: Optional ticker to filter by
            limit: Maximum results to return
            threshold: Minimum similarity threshold

        Returns:
            List of similar chunks with similarity scores
        """
        try:
            # Call the match_filing_chunks RPC function
            params = {
                "query_embedding": embedding,
                "match_threshold": threshold,
                "match_count": limit,
            }
            if ticker:
                params["filter_ticker"] = ticker.upper()

            result = self.client.rpc("match_filing_chunks", params).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error searching similar chunks: {e}")
            return []

    async def get_filing_chunks(
        self,
        ticker: str,
        accession_number: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get filing chunks for a ticker.

        Args:
            ticker: Stock ticker
            accession_number: Optional specific filing

        Returns:
            List of chunks
        """
        try:
            query = (
                self.client.table("filing_chunks")
                .select("*")
                .eq("ticker", ticker.upper())
            )
            if accession_number:
                query = query.eq("accession_number", accession_number)

            result = query.order("created_at", desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting filing chunks: {e}")
            return []

    async def delete_filing_chunks(
        self,
        ticker: str,
        accession_number: Optional[str] = None,
    ) -> int:
        """
        Delete filing chunks for a ticker.

        Args:
            ticker: Stock ticker
            accession_number: Optional specific filing

        Returns:
            Number of deleted chunks
        """
        try:
            query = (
                self.client.table("filing_chunks")
                .delete()
                .eq("ticker", ticker.upper())
            )
            if accession_number:
                query = query.eq("accession_number", accession_number)

            result = query.execute()
            count = len(result.data) if result.data else 0
            logger.info(f"Deleted {count} chunks for {ticker}")
            return count
        except Exception as e:
            logger.error(f"Error deleting filing chunks: {e}")
            return 0

    # ==================== User Management (Future) ====================

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        try:
            result = (
                self.client.table("users")
                .select("*")
                .eq("id", user_id)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    async def check_user_quota(self, user_id: str) -> Dict[str, Any]:
        """Check user's analysis quota."""
        try:
            user = await self.get_user(user_id)
            if not user:
                return {"allowed": False, "reason": "User not found"}

            tier = user.get("tier", "free")
            analyses_used = user.get("analyses_used", 0)

            if tier == "free" and analyses_used >= 1:
                return {
                    "allowed": False,
                    "reason": "Free tier limit reached",
                    "tier": tier,
                    "used": analyses_used,
                    "limit": 1,
                }

            return {
                "allowed": True,
                "tier": tier,
                "used": analyses_used,
                "limit": 1 if tier == "free" else -1,
            }
        except Exception as e:
            logger.error(f"Error checking user quota: {e}")
            return {"allowed": True}  # Fail open for now


# Singleton instance
supabase_service = SupabaseService()
