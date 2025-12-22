"""Neo4j service for graph database operations.

Stores: Companies, Signals, Filings, Relationships, Pattern matching
"""

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, AuthError
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import uuid

from app.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import DatabaseError

logger = get_logger(__name__)
settings = get_settings()


class Neo4jService:
    """
    Neo4j graph database service with connection pooling.

    Responsible for:
    - Storing company nodes
    - Storing signal nodes linked to filings
    - Pattern matching for similar companies
    - Bankruptcy pattern detection
    """

    def __init__(self):
        self._driver: Optional[AsyncDriver] = None
        self._initialized = False

    async def connect(self) -> None:
        """Establish connection to Neo4j with connection pooling."""
        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
            # Verify connection
            async with self._driver.session() as session:
                await session.run("RETURN 1")

            logger.info("Connected to Neo4j successfully")

            # Initialize schema
            await self._initialize_schema()
            self._initialized = True

        except AuthError as e:
            logger.error(f"Neo4j authentication failed: {e}")
            raise DatabaseError("Neo4j", "Authentication failed")
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            raise DatabaseError("Neo4j", "Service unavailable")
        except Exception as e:
            logger.error(f"Neo4j connection error: {e}")
            raise DatabaseError("Neo4j", str(e))

    async def close(self) -> None:
        """Close the Neo4j connection."""
        if self._driver:
            await self._driver.close()
            logger.info("Neo4j connection closed")

    async def health_check(self) -> bool:
        """Check if Neo4j connection is healthy."""
        if not self._driver:
            return False
        try:
            async with self._driver.session() as session:
                await session.run("RETURN 1")
            return True
        except Exception as e:
            logger.warning(f"Neo4j health check failed: {e}")
            return False

    @asynccontextmanager
    async def session(self):
        """Get a Neo4j session with automatic cleanup."""
        if not self._driver:
            raise DatabaseError("Neo4j", "Not connected")
        session = self._driver.session()
        try:
            yield session
        finally:
            await session.close()

    async def _initialize_schema(self) -> None:
        """Initialize Neo4j schema with constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE",
            "CREATE CONSTRAINT company_cik IF NOT EXISTS FOR (c:Company) REQUIRE c.cik IS UNIQUE",
            "CREATE CONSTRAINT filing_accession IF NOT EXISTS FOR (f:Filing) REQUIRE f.accession_number IS UNIQUE",
            "CREATE CONSTRAINT signal_id IF NOT EXISTS FOR (s:Signal) REQUIRE s.signal_id IS UNIQUE",
            "CREATE CONSTRAINT signal_type_name IF NOT EXISTS FOR (st:SignalType) REQUIRE st.name IS UNIQUE",
        ]

        indexes = [
            "CREATE INDEX company_status IF NOT EXISTS FOR (c:Company) ON (c.status)",
            "CREATE INDEX signal_type IF NOT EXISTS FOR (s:Signal) ON (s.type)",
            "CREATE INDEX signal_date IF NOT EXISTS FOR (s:Signal) ON (s.date)",
            "CREATE INDEX filing_type IF NOT EXISTS FOR (f:Filing) ON (f.filing_type)",
        ]

        async with self.session() as session:
            for constraint in constraints:
                try:
                    await session.run(constraint)
                except Exception as e:
                    logger.debug(f"Constraint may already exist: {e}")

            for index in indexes:
                try:
                    await session.run(index)
                except Exception as e:
                    logger.debug(f"Index may already exist: {e}")

            # Initialize signal types
            await self._initialize_signal_types(session)

        logger.info("Neo4j schema initialized")

    async def _initialize_signal_types(self, session) -> None:
        """Initialize SignalType nodes with weights."""
        signal_types = [
            ("GOING_CONCERN", "Financial", 25, "Auditor doubt about survival"),
            ("DEBT_DEFAULT", "Financial", 20, "Missed debt payments or acceleration"),
            ("CEO_DEPARTURE", "Leadership", 10, "CEO resignation or termination"),
            ("CFO_DEPARTURE", "Leadership", 10, "CFO resignation or termination"),
            ("MASS_LAYOFFS", "Operational", 15, "Workforce reduction >10%"),
            ("COVENANT_VIOLATION", "Financial", 12, "Loan covenant breach"),
            ("AUDITOR_CHANGE", "Governance", 8, "Change in external auditor"),
            ("BOARD_RESIGNATION", "Governance", 5, "Director departures"),
            ("DELISTING_WARNING", "Regulatory", 15, "Exchange compliance issues"),
            ("CREDIT_DOWNGRADE", "Financial", 10, "Rating agency downgrade"),
            ("ASSET_SALE", "Operational", 8, "Distressed asset sales"),
            ("RESTRUCTURING", "Operational", 10, "Formal restructuring plan"),
            ("SEC_INVESTIGATION", "Regulatory", 8, "SEC subpoena or enforcement"),
            ("MATERIAL_WEAKNESS", "Governance", 5, "Internal control failures"),
            ("EQUITY_DILUTION", "Financial", 5, "Emergency stock issuance"),
        ]

        query = """
        UNWIND $types as t
        MERGE (st:SignalType {name: t[0]})
        SET st.category = t[1],
            st.weight = t[2],
            st.description = t[3]
        """
        await session.run(query, types=signal_types)

    async def store_company(self, company_data: Dict[str, Any]) -> None:
        """
        Store or update a company node.

        Args:
            company_data: Dict with ticker, cik, name, status, risk_score
        """
        query = """
        MERGE (c:Company {ticker: $ticker})
        SET c.cik = $cik,
            c.name = $name,
            c.status = $status,
            c.risk_score = $risk_score,
            c.sector = $sector,
            c.updated_at = datetime()
        ON CREATE SET c.created_at = datetime()
        RETURN c
        """
        try:
            async with self.session() as session:
                await session.run(
                    query,
                    ticker=company_data.get("ticker"),
                    cik=company_data.get("cik"),
                    name=company_data.get("name", ""),
                    status=company_data.get("status", "ACTIVE"),
                    risk_score=company_data.get("risk_score", 0),
                    sector=company_data.get("sector", ""),
                )
            logger.info(f"Stored company: {company_data.get('ticker')}")
        except Exception as e:
            logger.error(f"Error storing company: {e}")
            raise DatabaseError("Neo4j", f"Failed to store company: {e}")

    async def store_filing(self, ticker: str, filing_data: Dict[str, Any]) -> None:
        """
        Store a filing node linked to a company.

        Args:
            ticker: Company ticker
            filing_data: Dict with accession_number, filing_type, filed_at, url
        """
        query = """
        MATCH (c:Company {ticker: $ticker})
        MERGE (f:Filing {accession_number: $accession_number})
        SET f.filing_type = $filing_type,
            f.filed_at = date($filed_at),
            f.url = $url,
            f.updated_at = datetime()
        MERGE (c)-[:FILED]->(f)
        RETURN f
        """
        try:
            async with self.session() as session:
                await session.run(
                    query,
                    ticker=ticker,
                    accession_number=filing_data.get("accession_number"),
                    filing_type=filing_data.get("filing_type"),
                    filed_at=filing_data.get("filed_at"),
                    url=filing_data.get("url", ""),
                )
        except Exception as e:
            logger.error(f"Error storing filing: {e}")
            raise DatabaseError("Neo4j", f"Failed to store filing: {e}")

    async def store_signal(
        self,
        ticker: str,
        filing_accession: str,
        signal_data: Dict[str, Any],
    ) -> str:
        """
        Store a signal node linked to a filing.

        Args:
            ticker: Company ticker
            filing_accession: Filing accession number
            signal_data: Signal data dict

        Returns:
            Signal ID
        """
        signal_id = signal_data.get("signal_id") or str(uuid.uuid4())

        query = """
        MATCH (c:Company {ticker: $ticker})-[:FILED]->(f:Filing {accession_number: $filing_accession})
        MERGE (s:Signal {signal_id: $signal_id})
        SET s.type = $type,
            s.severity = $severity,
            s.confidence = $confidence,
            s.evidence = $evidence,
            s.date = $date,
            s.item_number = $item_number,
            s.person = $person,
            s.detected_at = datetime()
        MERGE (f)-[:CONTAINS]->(s)
        WITH s
        MATCH (st:SignalType {name: $type})
        MERGE (s)-[:IS_TYPE]->(st)
        RETURN s.signal_id as signal_id
        """
        try:
            async with self.session() as session:
                result = await session.run(
                    query,
                    ticker=ticker,
                    filing_accession=filing_accession,
                    signal_id=signal_id,
                    type=signal_data.get("type"),
                    severity=signal_data.get("severity", 5),
                    confidence=signal_data.get("confidence", 0.8),
                    evidence=signal_data.get("evidence", ""),
                    date=signal_data.get("date"),
                    item_number=signal_data.get("item_number", ""),
                    person=signal_data.get("person"),
                )
                record = await result.single()
                return record["signal_id"] if record else signal_id
        except Exception as e:
            logger.error(f"Error storing signal: {e}")
            raise DatabaseError("Neo4j", f"Failed to store signal: {e}")

    async def get_company_signals(self, ticker: str) -> List[Dict[str, Any]]:
        """Get all signals for a company."""
        query = """
        MATCH (c:Company {ticker: $ticker})-[:FILED]->(f:Filing)-[:CONTAINS]->(s:Signal)
        RETURN s.signal_id as id,
               s.type as type,
               s.severity as severity,
               s.confidence as confidence,
               s.evidence as evidence,
               s.date as date,
               s.item_number as item_number,
               s.person as person,
               f.accession_number as filing_accession,
               f.filing_type as filing_type
        ORDER BY s.date DESC
        """
        try:
            async with self.session() as session:
                result = await session.run(query, ticker=ticker)
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Error getting company signals: {e}")
            return []

    async def find_similar_companies(
        self, ticker: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find companies with similar signal patterns."""
        query = """
        MATCH (c1:Company {ticker: $ticker})-[:FILED]->(:Filing)-[:CONTAINS]->(s1:Signal)
        WITH c1, COLLECT(DISTINCT s1.type) as target_signals
        MATCH (c2:Company)-[:FILED]->(:Filing)-[:CONTAINS]->(s2:Signal)
        WHERE c1 <> c2
        WITH c1, target_signals, c2, COLLECT(DISTINCT s2.type) as other_signals
        WITH c2,
             [x IN target_signals WHERE x IN other_signals] as common,
             target_signals, other_signals
        WHERE SIZE(common) >= 2
        RETURN c2.ticker as ticker,
               c2.name as name,
               c2.status as status,
               c2.risk_score as risk_score,
               SIZE(common) as common_signals,
               common as common_signal_types,
               SIZE(common) * 1.0 / SIZE(other_signals) as similarity_score
        ORDER BY similarity_score DESC, common_signals DESC
        LIMIT $limit
        """
        try:
            async with self.session() as session:
                result = await session.run(query, ticker=ticker, limit=limit)
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Error finding similar companies: {e}")
            return []

    async def match_bankruptcy_patterns(
        self, ticker: str
    ) -> List[Dict[str, Any]]:
        """Match signal patterns to known bankruptcy cases."""
        query = """
        MATCH (target:Company {ticker: $ticker})-[:FILED]->(:Filing)-[:CONTAINS]->(s:Signal)
        WITH target, COLLECT(DISTINCT s.type) as target_signals

        MATCH (bankrupt:Company {status: 'BANKRUPT'})-[:FILED]->(:Filing)-[:CONTAINS]->(bs:Signal)
        WITH target, target_signals, bankrupt, COLLECT(DISTINCT bs.type) as bankrupt_signals

        WITH target, bankrupt,
             [x IN target_signals WHERE x IN bankrupt_signals] as common,
             target_signals, bankrupt_signals
        WHERE SIZE(common) >= 2

        RETURN bankrupt.ticker as ticker,
               bankrupt.name as name,
               bankrupt.bankruptcy_date as bankruptcy_date,
               SIZE(common) as matching_signals,
               common as common_signal_types,
               SIZE(common) * 1.0 / SIZE(bankrupt_signals) as similarity_score
        ORDER BY similarity_score DESC
        LIMIT 3
        """
        try:
            async with self.session() as session:
                result = await session.run(query, ticker=ticker)
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Error matching bankruptcy patterns: {e}")
            return []

    async def add_known_bankruptcy(
        self,
        ticker: str,
        cik: str,
        name: str,
        bankruptcy_date: str,
        signals: List[Dict[str, Any]],
    ) -> None:
        """
        Add a known bankruptcy case for pattern matching.

        Args:
            ticker: Company ticker
            cik: Company CIK
            name: Company name
            bankruptcy_date: Date of bankruptcy filing
            signals: List of signals that preceded the bankruptcy
        """
        # Store company as bankrupt
        await self.store_company({
            "ticker": ticker,
            "cik": cik,
            "name": name,
            "status": "BANKRUPT",
            "risk_score": 100,
        })

        # Update with bankruptcy date
        query = """
        MATCH (c:Company {ticker: $ticker})
        SET c.bankruptcy_date = date($bankruptcy_date)
        """
        async with self.session() as session:
            await session.run(query, ticker=ticker, bankruptcy_date=bankruptcy_date)

        logger.info(f"Added known bankruptcy case: {ticker}")


# Singleton instance
neo4j_service = Neo4jService()
