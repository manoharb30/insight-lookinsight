"""Neo4j Repository - Facts-only queries, no scoring."""

from typing import List, Optional, Dict, Any
from app.services.neo4j_service import neo4j_service
from app.models.timeline_models import (
    CompanyNode, SignalNode, FilingNode,
    CompanyTimeline, CompanyInfo, SignalDetail, FilingDetail, FilingInfo,
    SimilarCase, GoingConcernHistory, GoingConcernYear
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class Neo4jRepository:
    """Repository for Neo4j timeline operations - facts only, no scores."""

    # ==================== COMPANY OPERATIONS ====================

    async def upsert_company(self, company: CompanyNode) -> bool:
        """Create or update company node - NO SCORES."""
        query = """
        MERGE (c:Company {ticker: $ticker})
        SET c.name = $name,
            c.cik = $cik,
            c.status = $status,
            c.bankruptcy_date = CASE WHEN $bankruptcy_date IS NOT NULL
                THEN date($bankruptcy_date) ELSE null END,
            c.going_concern_status = $going_concern_status,
            c.going_concern_first_seen = CASE WHEN $going_concern_first_seen IS NOT NULL
                THEN date($going_concern_first_seen) ELSE null END,
            c.going_concern_last_seen = CASE WHEN $going_concern_last_seen IS NOT NULL
                THEN date($going_concern_last_seen) ELSE null END,
            c.updated_at = datetime()
        RETURN c
        """
        try:
            async with neo4j_service.session() as session:
                await session.run(
                    query,
                    ticker=company.ticker,
                    name=company.name,
                    cik=company.cik,
                    status=company.status,
                    bankruptcy_date=company.bankruptcy_date,
                    going_concern_status=company.going_concern_status,
                    going_concern_first_seen=company.going_concern_first_seen,
                    going_concern_last_seen=company.going_concern_last_seen
                )
                return True
        except Exception as e:
            logger.error(f"Error upserting company {company.ticker}: {e}")
            return False

    async def update_company_signal_stats(self, ticker: str) -> bool:
        """Update company's signal statistics (no scores)."""
        query = """
        MATCH (c:Company {ticker: $ticker})
        OPTIONAL MATCH (c)-[:HAS_SIGNAL]->(s:Signal)
        WITH c,
             min(s.date) as first_signal,
             max(s.date) as last_signal,
             count(s) as signal_count
        SET c.first_signal_date = first_signal,
            c.last_signal_date = last_signal,
            c.total_signals = signal_count,
            c.days_since_last_signal = CASE
                WHEN last_signal IS NOT NULL
                THEN duration.inDays(last_signal, date()).days
                ELSE null
            END
        RETURN c
        """
        try:
            async with neo4j_service.session() as session:
                await session.run(query, ticker=ticker)
                return True
        except Exception as e:
            logger.error(f"Error updating signal stats for {ticker}: {e}")
            return False

    # ==================== SIGNAL OPERATIONS ====================

    async def create_signal(
        self,
        ticker: str,
        signal: SignalNode,
        filing: FilingNode
    ) -> bool:
        """Create signal node with filing and link to company."""
        query = """
        MATCH (c:Company {ticker: $ticker})

        MERGE (f:Filing {accession: $accession})
        SET f.type = $filing_type,
            f.item = $item,
            f.date = CASE WHEN $filing_date IS NOT NULL AND $filing_date <> ''
                THEN date($filing_date) ELSE null END,
            f.url = $url,
            f.fiscal_year = $fiscal_year,
            f.category = $category,
            f.summary = $summary,
            f.has_going_concern = $has_going_concern,
            f.has_material_weakness = $has_material_weakness

        MERGE (s:Signal {id: $signal_id})
        SET s.type = $signal_type,
            s.date = CASE WHEN $signal_date IS NOT NULL AND $signal_date <> ''
                THEN date($signal_date) ELSE null END,
            s.evidence = $evidence,
            s.fiscal_year = $signal_fiscal_year,
            s.created_at = datetime()

        MERGE (c)-[:HAS_SIGNAL]->(s)
        MERGE (s)-[:EXTRACTED_FROM]->(f)
        MERGE (c)-[:FILED]->(f)

        RETURN s.id as signal_id
        """
        try:
            async with neo4j_service.session() as session:
                await session.run(
                    query,
                    ticker=ticker,
                    accession=filing.accession,
                    filing_type=filing.type,
                    item=filing.item,
                    filing_date=filing.date,
                    url=filing.url,
                    fiscal_year=filing.fiscal_year,
                    category=filing.category,
                    summary=filing.summary,
                    has_going_concern=filing.has_going_concern,
                    has_material_weakness=filing.has_material_weakness,
                    signal_id=signal.id,
                    signal_type=signal.type,
                    signal_date=signal.date,
                    evidence=signal.evidence,
                    signal_fiscal_year=signal.fiscal_year
                )
                return True
        except Exception as e:
            logger.error(f"Error creating signal for {ticker}: {e}")
            return False

    async def build_signal_chain(self, ticker: str) -> int:
        """Create NEXT relationships between signals chronologically."""
        query = """
        MATCH (c:Company {ticker: $ticker})-[:HAS_SIGNAL]->(s:Signal)
        WHERE s.date IS NOT NULL
        WITH s ORDER BY s.date
        WITH collect(s) as signals
        UNWIND range(0, size(signals)-2) as i
        WITH signals[i] as s1, signals[i+1] as s2
        MERGE (s1)-[r:NEXT]->(s2)
        SET r.days = duration.inDays(s1.date, s2.date).days
        RETURN count(r) as relationships_created
        """
        try:
            async with neo4j_service.session() as session:
                result = await session.run(query, ticker=ticker)
                record = await result.single()
                return record["relationships_created"] if record else 0
        except Exception as e:
            logger.error(f"Error building signal chain for {ticker}: {e}")
            return 0

    # ==================== FILING OPERATIONS ====================

    async def create_filing(self, ticker: str, filing: FilingNode) -> bool:
        """Create filing node (for routine filings without signals)."""
        query = """
        MATCH (c:Company {ticker: $ticker})

        MERGE (f:Filing {accession: $accession})
        SET f.type = $type,
            f.item = $item,
            f.date = CASE WHEN $date IS NOT NULL AND $date <> ''
                THEN date($date) ELSE null END,
            f.url = $url,
            f.fiscal_year = $fiscal_year,
            f.category = $category,
            f.summary = $summary,
            f.has_going_concern = $has_going_concern,
            f.has_material_weakness = $has_material_weakness

        MERGE (c)-[:FILED]->(f)

        RETURN f.accession as accession
        """
        try:
            async with neo4j_service.session() as session:
                await session.run(
                    query,
                    ticker=ticker,
                    accession=filing.accession,
                    type=filing.type,
                    item=filing.item,
                    date=filing.date,
                    url=filing.url,
                    fiscal_year=filing.fiscal_year,
                    category=filing.category,
                    summary=filing.summary,
                    has_going_concern=filing.has_going_concern,
                    has_material_weakness=filing.has_material_weakness
                )
                return True
        except Exception as e:
            logger.error(f"Error creating filing for {ticker}: {e}")
            return False

    # ==================== TIMELINE QUERIES ====================

    async def get_company_timeline(self, ticker: str) -> Optional[CompanyTimeline]:
        """Get complete signal timeline for a company - NO SCORES."""
        query = """
        MATCH (c:Company {ticker: $ticker})

        // Get all signals with their filings
        OPTIONAL MATCH (c)-[:HAS_SIGNAL]->(s:Signal)
        OPTIONAL MATCH (s)-[:EXTRACTED_FROM]->(sf:Filing)
        OPTIONAL MATCH (s)-[next:NEXT]->(:Signal)

        WITH c, s, sf, next
        ORDER BY s.date

        WITH c, collect(DISTINCT {
            id: s.id,
            type: s.type,
            date: toString(s.date),
            evidence: s.evidence,
            fiscal_year: s.fiscal_year,
            days_to_next: next.days,
            filing: {
                type: sf.type,
                item: sf.item,
                date: toString(sf.date),
                url: sf.url,
                accession: sf.accession
            }
        }) as signals

        // Get recent filings (last 12 months)
        OPTIONAL MATCH (c)-[:FILED]->(rf:Filing)
        WHERE rf.date >= date() - duration('P12M')

        WITH c, signals, rf
        ORDER BY rf.date DESC

        WITH c, signals, collect(DISTINCT {
            accession: rf.accession,
            type: rf.type,
            item: rf.item,
            date: toString(rf.date),
            url: rf.url,
            category: rf.category,
            summary: rf.summary
        }) as recent_filings

        RETURN {
            ticker: c.ticker,
            name: c.name,
            cik: c.cik,
            status: c.status,
            bankruptcy_date: toString(c.bankruptcy_date),
            first_signal_date: toString(c.first_signal_date),
            last_signal_date: toString(c.last_signal_date),
            days_since_last_signal: c.days_since_last_signal,
            total_signals: c.total_signals,
            going_concern_status: c.going_concern_status,
            going_concern_first_seen: toString(c.going_concern_first_seen),
            going_concern_last_seen: toString(c.going_concern_last_seen)
        } as company,
        signals,
        recent_filings
        """
        try:
            async with neo4j_service.session() as session:
                result = await session.run(query, ticker=ticker)
                record = await result.single()

                if not record:
                    return None

                company_data = record["company"]
                signals_data = record["signals"]
                filings_data = record["recent_filings"]

                # Build company info
                company = CompanyInfo(
                    ticker=company_data.get("ticker", ticker),
                    name=company_data.get("name", ""),
                    cik=company_data.get("cik"),
                    status=company_data.get("status", "ACTIVE"),
                    bankruptcy_date=company_data.get("bankruptcy_date"),
                    first_signal_date=company_data.get("first_signal_date"),
                    last_signal_date=company_data.get("last_signal_date"),
                    days_since_last_signal=company_data.get("days_since_last_signal"),
                    total_signals=company_data.get("total_signals") or 0,
                    going_concern_status=company_data.get("going_concern_status", "NEVER"),
                    going_concern_first_seen=company_data.get("going_concern_first_seen"),
                    going_concern_last_seen=company_data.get("going_concern_last_seen")
                )

                # Build signals list
                signals = []
                for s in signals_data:
                    if s.get("id"):
                        filing_data = s.get("filing", {})
                        filing = None
                        if filing_data.get("accession"):
                            filing = FilingInfo(
                                type=filing_data.get("type", "8-K"),
                                item=filing_data.get("item"),
                                date=filing_data.get("date", ""),
                                url=filing_data.get("url"),
                                accession=filing_data.get("accession")
                            )
                        signals.append(SignalDetail(
                            id=s["id"],
                            type=s.get("type", "UNKNOWN"),
                            date=s.get("date", ""),
                            evidence=s.get("evidence", ""),
                            fiscal_year=s.get("fiscal_year"),
                            days_to_next=s.get("days_to_next"),
                            filing=filing
                        ))

                # Build recent filings list
                recent_filings = []
                for f in filings_data:
                    if f.get("accession"):
                        recent_filings.append(FilingDetail(
                            accession=f["accession"],
                            type=f.get("type", "8-K"),
                            item=f.get("item"),
                            date=f.get("date", ""),
                            url=f.get("url"),
                            category=f.get("category", "ROUTINE"),
                            summary=f.get("summary")
                        ))

                return CompanyTimeline(
                    company=company,
                    signals=signals,
                    recent_filings=recent_filings
                )

        except Exception as e:
            logger.error(f"Error getting timeline for {ticker}: {e}")
            return None

    async def get_going_concern_history(self, ticker: str) -> GoingConcernHistory:
        """Track going concern status across 10-K filings."""
        query = """
        MATCH (c:Company {ticker: $ticker})-[:FILED]->(f:Filing)
        WHERE f.type = '10-K' AND f.has_going_concern IS NOT NULL
        RETURN f.fiscal_year as fiscal_year,
               f.has_going_concern as has_going_concern,
               toString(f.date) as filing_date,
               f.url as url
        ORDER BY f.fiscal_year DESC
        """
        try:
            async with neo4j_service.session() as session:
                result = await session.run(query, ticker=ticker)
                records = await result.data()

                years = []
                for r in records:
                    years.append(GoingConcernYear(
                        fiscal_year=r["fiscal_year"],
                        has_going_concern=r["has_going_concern"],
                        filing_date=r["filing_date"] or "",
                        url=r.get("url")
                    ))

                return GoingConcernHistory(ticker=ticker, years=years)

        except Exception as e:
            logger.error(f"Error getting going concern history for {ticker}: {e}")
            return GoingConcernHistory(ticker=ticker, years=[])

    async def get_recent_filings(
        self,
        ticker: str,
        months: int = 12,
        category: Optional[str] = None
    ) -> List[FilingDetail]:
        """Get recent filings for a company."""
        query = f"""
        MATCH (c:Company {{ticker: $ticker}})-[:FILED]->(f:Filing)
        WHERE f.date >= date() - duration('P{months}M')
        {"AND f.category = $category" if category else ""}
        RETURN f
        ORDER BY f.date DESC
        """
        try:
            params = {"ticker": ticker}
            if category:
                params["category"] = category

            async with neo4j_service.session() as session:
                result = await session.run(query, **params)
                records = await result.data()

                return [
                    FilingDetail(
                        accession=r["f"].get("accession", ""),
                        type=r["f"].get("type", "8-K"),
                        item=r["f"].get("item"),
                        date=str(r["f"].get("date", "")),
                        url=r["f"].get("url"),
                        category=r["f"].get("category", "ROUTINE"),
                        summary=r["f"].get("summary")
                    )
                    for r in records
                ]

        except Exception as e:
            logger.error(f"Error getting recent filings for {ticker}: {e}")
            return []

    # ==================== COMPARISON QUERIES ====================

    async def get_similar_cases(
        self,
        ticker: str,
        min_overlap: int = 2
    ) -> List[SimilarCase]:
        """Find historical cases with similar signal patterns."""
        query = """
        MATCH (target:Company {ticker: $ticker})-[:HAS_SIGNAL]->(ts:Signal)
        WITH target, collect(DISTINCT ts.type) as targetSignals

        MATCH (other:Company)-[:HAS_SIGNAL]->(os:Signal)
        WHERE other <> target
          AND other.status IS NOT NULL
        WITH target, targetSignals, other, collect(DISTINCT os.type) as otherSignals

        WITH other, targetSignals, otherSignals,
             [x IN targetSignals WHERE x IN otherSignals] as overlap

        WHERE size(overlap) >= $min_overlap

        // Get timeline for similar companies
        OPTIONAL MATCH (other)-[:HAS_SIGNAL]->(s:Signal)
        WITH other, overlap, otherSignals, s
        ORDER BY s.date

        RETURN other.ticker as ticker,
               other.name as name,
               other.status as outcome,
               toString(other.bankruptcy_date) as bankruptcy_date,
               other.going_concern_status as going_concern_status,
               size(overlap) as overlap_count,
               overlap as matching_signals,
               collect({
                   type: s.type,
                   date: toString(s.date)
               }) as timeline
        ORDER BY overlap_count DESC
        LIMIT 10
        """
        try:
            async with neo4j_service.session() as session:
                result = await session.run(query, ticker=ticker, min_overlap=min_overlap)
                records = await result.data()

                return [
                    SimilarCase(
                        ticker=r["ticker"],
                        name=r["name"] or "",
                        outcome=r["outcome"] or "ACTIVE",
                        bankruptcy_date=r["bankruptcy_date"],
                        going_concern_status=r["going_concern_status"],
                        overlap_count=r["overlap_count"],
                        matching_signals=r["matching_signals"] or [],
                        timeline=r["timeline"] or []
                    )
                    for r in records
                ]

        except Exception as e:
            logger.error(f"Error getting similar cases for {ticker}: {e}")
            return []

    async def get_companies_by_signal_recency(self) -> Dict[str, List[dict]]:
        """Group companies by how recent their last signal was."""
        query = """
        MATCH (c:Company)
        WHERE c.last_signal_date IS NOT NULL
        WITH c, duration.inDays(c.last_signal_date, date()).days as days_since
        RETURN
            CASE
                WHEN days_since <= 30 THEN 'last_30_days'
                WHEN days_since <= 90 THEN 'last_90_days'
                WHEN days_since <= 180 THEN 'last_180_days'
                ELSE 'over_180_days'
            END as recency_bucket,
            collect({
                ticker: c.ticker,
                name: c.name,
                days_since: days_since,
                last_signal: toString(c.last_signal_date),
                going_concern_status: c.going_concern_status
            }) as companies
        """
        try:
            async with neo4j_service.session() as session:
                result = await session.run(query)
                records = await result.data()
                return {r["recency_bucket"]: r["companies"] for r in records}

        except Exception as e:
            logger.error(f"Error getting companies by recency: {e}")
            return {}


# Singleton instance
neo4j_repository = Neo4jRepository()
