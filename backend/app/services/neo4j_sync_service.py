"""Neo4j Sync Service - Syncs signals from analysis pipeline to Neo4j.

Facts-only approach: stores signals with evidence and filing context.
No scoring, no risk predictions.
"""

from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime, timedelta

from app.repositories.neo4j_repository import neo4j_repository
from app.models.timeline_models import CompanyNode, SignalNode, FilingNode
from app.services.supabase_service import supabase_service
from app.core.logging import get_logger

logger = get_logger(__name__)


class Neo4jSyncService:
    """Service for syncing analysis results to Neo4j timeline graph."""

    def __init__(self):
        self.repo = neo4j_repository

    async def sync_from_analysis(
        self,
        ticker: str,
        company_data: Dict[str, Any],
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Sync analysis results to Neo4j.

        Args:
            ticker: Company ticker
            company_data: Dict with cik, name, etc.
            signals: List of signal dicts from extraction

        Returns:
            Sync result with counts
        """
        ticker = ticker.upper()

        # 1. Determine going concern status from signals
        gc_status = self._determine_going_concern_status(signals)

        # 2. Create company node (facts only, no scores)
        company_node = CompanyNode(
            ticker=ticker,
            name=company_data.get("name", company_data.get("company_name", ticker)),
            cik=company_data.get("cik", ""),
            status=company_data.get("status", "ACTIVE"),
            bankruptcy_date=company_data.get("bankruptcy_date"),
            going_concern_status=gc_status["status"],
            going_concern_first_seen=gc_status.get("first_seen"),
            going_concern_last_seen=gc_status.get("last_seen"),
        )

        await self.repo.upsert_company(company_node)
        logger.info(f"Upserted company {ticker} with going_concern_status={gc_status['status']}")

        # 3. Create signal nodes with filings
        signals_created = 0
        for signal_data in signals:
            if not signal_data.get("type"):
                continue

            signal_node = SignalNode(
                id=signal_data.get("signal_id") or signal_data.get("id") or str(uuid4()),
                type=signal_data["type"],
                date=signal_data.get("date", ""),
                evidence=signal_data.get("evidence", ""),
                fiscal_year=signal_data.get("fiscal_year") or self._extract_year(signal_data.get("date", "")),
            )

            filing_node = FilingNode(
                accession=signal_data.get("filing_accession") or f"unknown-{uuid4()}",
                type=signal_data.get("filing_type", "8-K"),
                item=signal_data.get("item_number"),
                date=signal_data.get("filing_date") or signal_data.get("date", ""),
                url=signal_data.get("filing_url", ""),
                fiscal_year=signal_data.get("fiscal_year") or self._extract_year(signal_data.get("date", "")),
                category="DISTRESS",
                summary=f"{signal_data['type']} detected",
                has_going_concern=signal_data["type"] == "GOING_CONCERN",
                has_material_weakness=signal_data["type"] == "MATERIAL_WEAKNESS",
            )

            success = await self.repo.create_signal(ticker, signal_node, filing_node)
            if success:
                signals_created += 1

        # 4. Build signal chain (NEXT relationships)
        chain_count = 0
        if signals_created > 1:
            chain_count = await self.repo.build_signal_chain(ticker)

        # 5. Update company stats
        await self.repo.update_company_signal_stats(ticker)

        result = {
            "ticker": ticker,
            "signals_created": signals_created,
            "chain_relationships": chain_count,
            "going_concern_status": gc_status["status"],
        }
        logger.info(f"Sync complete for {ticker}: {result}")
        return result

    async def sync_filing(
        self,
        ticker: str,
        filing_data: Dict[str, Any],
        category: str = "ROUTINE",
    ) -> bool:
        """
        Sync a single filing (can be routine or distress).

        Args:
            ticker: Company ticker
            filing_data: Filing data dict
            category: DISTRESS, ROUTINE, or CORPORATE_ACTION

        Returns:
            Success boolean
        """
        filing_node = FilingNode(
            accession=filing_data.get("accession") or filing_data.get("accession_number", ""),
            type=filing_data.get("type") or filing_data.get("filing_type", "8-K"),
            item=filing_data.get("item") or filing_data.get("item_number"),
            date=filing_data.get("date") or filing_data.get("filed_at", ""),
            url=filing_data.get("url", ""),
            fiscal_year=filing_data.get("fiscal_year") or self._extract_year(filing_data.get("date", "")),
            category=category,
            summary=filing_data.get("summary", ""),
            has_going_concern=filing_data.get("has_going_concern"),
            has_material_weakness=filing_data.get("has_material_weakness"),
        )

        return await self.repo.create_filing(ticker.upper(), filing_node)

    async def sync_routine_filings(
        self,
        ticker: str,
        filings: List[Dict[str, Any]],
    ) -> int:
        """
        Sync routine (non-distress) filings for context.

        Args:
            ticker: Company ticker
            filings: List of filing dicts

        Returns:
            Number of filings synced
        """
        count = 0
        for filing_data in filings:
            # Determine category based on filing content
            category = self._categorize_filing(filing_data)
            if await self.sync_filing(ticker, filing_data, category):
                count += 1
        return count

    async def sync_from_supabase(self, ticker: str) -> Dict[str, Any]:
        """
        Sync a company's data from Supabase to Neo4j.

        Args:
            ticker: Company ticker

        Returns:
            Sync result
        """
        ticker = ticker.upper()

        # Get cached analysis from Supabase
        analysis = await supabase_service.get_cached_analysis(ticker)
        if not analysis:
            return {"error": f"No cached analysis found for {ticker}"}

        result_data = analysis.get("result", {})
        signals = result_data.get("signals", [])

        return await self.sync_from_analysis(
            ticker=ticker,
            company_data={
                "cik": analysis.get("cik", ""),
                "name": analysis.get("company_name", ticker),
                "status": "ACTIVE",
            },
            signals=signals,
        )

    def _determine_going_concern_status(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Determine going concern status based on signal history.

        Returns:
        - status: "ACTIVE" | "REMOVED" | "NEVER"
        - first_seen: date when first appeared
        - last_seen: date when last appeared
        """
        gc_signals = [s for s in signals if s.get("type") == "GOING_CONCERN"]

        if not gc_signals:
            return {"status": "NEVER"}

        # Sort by date
        gc_signals_sorted = sorted(
            [s for s in gc_signals if s.get("date")],
            key=lambda x: x["date"]
        )

        if not gc_signals_sorted:
            return {"status": "NEVER"}

        first_seen = gc_signals_sorted[0]["date"]
        last_seen = gc_signals_sorted[-1]["date"]

        # Determine if going concern is still active
        # If last going concern was more than 15 months ago, likely removed
        # (10-K is annual, so 15 months gives buffer)
        try:
            last_gc_date = datetime.fromisoformat(last_seen.replace("Z", "+00:00").replace("T", " ").split("+")[0].split(" ")[0])
            days_since = (datetime.now() - last_gc_date).days

            if days_since > 450:  # ~15 months
                return {
                    "status": "REMOVED",
                    "first_seen": first_seen[:10] if first_seen else None,
                    "last_seen": last_seen[:10] if last_seen else None,
                }
            else:
                return {
                    "status": "ACTIVE",
                    "first_seen": first_seen[:10] if first_seen else None,
                    "last_seen": last_seen[:10] if last_seen else None,
                }
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing going concern dates: {e}")
            return {
                "status": "ACTIVE",
                "first_seen": first_seen[:10] if first_seen else None,
                "last_seen": last_seen[:10] if last_seen else None,
            }

    def _categorize_filing(self, filing_data: Dict[str, Any]) -> str:
        """Categorize a filing based on its content."""
        item = filing_data.get("item") or filing_data.get("item_number", "")
        summary = (filing_data.get("summary") or "").lower()

        # Distress indicators
        distress_items = ["4.02", "2.05", "2.06", "5.02"]
        if item in distress_items:
            return "DISTRESS"

        # Corporate action indicators
        corporate_items = ["1.01", "1.02", "2.01", "3.02"]
        corporate_keywords = ["acquisition", "merger", "split", "financing", "offering"]
        if item in corporate_items or any(kw in summary for kw in corporate_keywords):
            return "CORPORATE_ACTION"

        # Default to routine
        return "ROUTINE"

    def _extract_year(self, date_str: str) -> int:
        """Extract year from date string."""
        if not date_str:
            return datetime.now().year
        try:
            return int(date_str[:4])
        except (ValueError, IndexError):
            return datetime.now().year


# Singleton instance
neo4j_sync_service = Neo4jSyncService()
