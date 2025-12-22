from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Optional
from app.config import get_settings

settings = get_settings()


class Neo4jService:
    def __init__(self):
        self.driver = None

    async def connect(self):
        """Connect to Neo4j Aura."""
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )

    async def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            await self.driver.close()

    async def health_check(self) -> bool:
        """Check if Neo4j connection is healthy."""
        if not self.driver:
            return False
        try:
            async with self.driver.session() as session:
                await session.run("RETURN 1")
            return True
        except Exception:
            return False

    async def store_company(self, company_data: Dict[str, Any]):
        """Store or update a company node."""
        query = """
        MERGE (c:Company {ticker: $ticker})
        SET c.cik = $cik,
            c.name = $name,
            c.status = $status,
            c.risk_score = $risk_score,
            c.updated_at = datetime()
        RETURN c
        """
        async with self.driver.session() as session:
            await session.run(query, **company_data)

    async def store_signal(
        self,
        ticker: str,
        filing_accession: str,
        signal_data: Dict[str, Any],
    ):
        """Store a signal and link to company and filing."""
        query = """
        MATCH (c:Company {ticker: $ticker})
        MERGE (f:Filing {accession_number: $filing_accession})
        MERGE (c)-[:FILED]->(f)

        CREATE (s:Signal {
            signal_id: $signal_id,
            type: $type,
            severity: $severity,
            confidence: $confidence,
            evidence: $evidence,
            date: $date,
            detected_at: datetime()
        })

        CREATE (f)-[:CONTAINS]->(s)

        MERGE (st:SignalType {name: $type})
        CREATE (s)-[:IS_TYPE]->(st)

        RETURN s
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                ticker=ticker,
                filing_accession=filing_accession,
                **signal_data,
            )

    async def find_similar_companies(
        self, ticker: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find companies with similar signal patterns."""
        query = """
        MATCH (c1:Company {ticker: $ticker})-[:FILED]->(:Filing)-[:CONTAINS]->(s1:Signal)
        MATCH (c2:Company)-[:FILED]->(:Filing)-[:CONTAINS]->(s2:Signal)
        WHERE c1 <> c2 AND s1.type = s2.type
        WITH c1, c2, COUNT(DISTINCT s1.type) as common_signals
        WHERE common_signals >= 2
        RETURN c2.ticker as ticker,
               c2.name as name,
               c2.status as status,
               c2.risk_score as risk_score,
               common_signals
        ORDER BY common_signals DESC
        LIMIT $limit
        """
        async with self.driver.session() as session:
            result = await session.run(query, ticker=ticker, limit=limit)
            records = await result.data()
            return records

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
        async with self.driver.session() as session:
            result = await session.run(query, ticker=ticker)
            records = await result.data()
            return records

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
               f.accession_number as filing_accession
        ORDER BY s.date DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query, ticker=ticker)
            records = await result.data()
            return records

    async def initialize_signal_types(self):
        """Initialize the SignalType nodes."""
        signal_types = [
            ("GOING_CONCERN", "Financial", 25),
            ("CEO_DEPARTURE", "Leadership", 10),
            ("CFO_DEPARTURE", "Leadership", 10),
            ("MASS_LAYOFFS", "Operational", 15),
            ("DEBT_DEFAULT", "Financial", 20),
            ("COVENANT_VIOLATION", "Financial", 12),
            ("AUDITOR_CHANGE", "Governance", 8),
            ("BOARD_RESIGNATION", "Governance", 5),
            ("DELISTING_WARNING", "Regulatory", 15),
            ("CREDIT_DOWNGRADE", "Financial", 10),
            ("ASSET_SALE", "Operational", 8),
            ("RESTRUCTURING", "Operational", 10),
            ("SEC_INVESTIGATION", "Regulatory", 8),
            ("MATERIAL_WEAKNESS", "Governance", 5),
            ("EQUITY_DILUTION", "Financial", 5),
        ]

        query = """
        UNWIND $types as t
        MERGE (st:SignalType {name: t[0]})
        SET st.category = t[1], st.weight = t[2]
        """
        async with self.driver.session() as session:
            await session.run(query, types=signal_types)


# Singleton instance
neo4j_service = Neo4jService()
