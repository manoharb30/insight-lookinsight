"""Seed known bankruptcy cases into Neo4j for pattern matching."""

import asyncio
from datetime import datetime

from app.services.neo4j_service import neo4j_service
from app.core.logging import get_logger

logger = get_logger(__name__)

# Known bankruptcy cases with their pre-bankruptcy signals
BANKRUPTCY_CASES = [
    {
        "ticker": "IRBT",
        "cik": "0001159167",
        "name": "iRobot Corporation",
        "bankruptcy_date": "2024-12-14",
        "sector": "Consumer Electronics",
        "signals": [
            {"type": "CEO_DEPARTURE", "date": "2024-01-29", "severity": 8},
            {"type": "MASS_LAYOFFS", "date": "2024-01-29", "severity": 9},
            {"type": "CFO_DEPARTURE", "date": "2024-04-08", "severity": 7},
            {"type": "GOING_CONCERN", "date": "2024-05-07", "severity": 9},
            {"type": "RESTRUCTURING", "date": "2024-01-29", "severity": 7},
            {"type": "DEBT_DEFAULT", "date": "2024-08-12", "severity": 8},
            {"type": "AUDITOR_CHANGE", "date": "2024-04-23", "severity": 6},
            {"type": "BOARD_RESIGNATION", "date": "2024-03-15", "severity": 5},
            {"type": "CREDIT_DOWNGRADE", "date": "2024-02-01", "severity": 7},
            {"type": "ASSET_SALE", "date": "2024-09-30", "severity": 8},
        ],
    },
    {
        "ticker": "WEWORK",
        "cik": "0001813756",
        "name": "WeWork Inc.",
        "bankruptcy_date": "2023-11-06",
        "sector": "Real Estate",
        "signals": [
            {"type": "GOING_CONCERN", "date": "2023-08-08", "severity": 9},
            {"type": "CEO_DEPARTURE", "date": "2023-05-26", "severity": 7},
            {"type": "MASS_LAYOFFS", "date": "2022-11-10", "severity": 8},
            {"type": "RESTRUCTURING", "date": "2023-03-28", "severity": 7},
            {"type": "DEBT_DEFAULT", "date": "2023-09-15", "severity": 9},
            {"type": "DELISTING_WARNING", "date": "2023-04-05", "severity": 7},
            {"type": "ASSET_SALE", "date": "2023-06-20", "severity": 7},
            {"type": "EQUITY_DILUTION", "date": "2022-09-15", "severity": 6},
        ],
    },
    {
        "ticker": "BBBYQ",
        "cik": "0000886158",
        "name": "Bed Bath & Beyond Inc.",
        "bankruptcy_date": "2023-04-23",
        "sector": "Retail",
        "signals": [
            {"type": "GOING_CONCERN", "date": "2023-01-05", "severity": 9},
            {"type": "CEO_DEPARTURE", "date": "2022-06-29", "severity": 8},
            {"type": "CFO_DEPARTURE", "date": "2022-09-04", "severity": 9},
            {"type": "MASS_LAYOFFS", "date": "2022-08-31", "severity": 8},
            {"type": "DEBT_DEFAULT", "date": "2023-02-06", "severity": 9},
            {"type": "DELISTING_WARNING", "date": "2023-01-18", "severity": 8},
            {"type": "ASSET_SALE", "date": "2023-01-26", "severity": 7},
            {"type": "RESTRUCTURING", "date": "2022-08-31", "severity": 7},
            {"type": "EQUITY_DILUTION", "date": "2023-02-07", "severity": 8},
            {"type": "BOARD_RESIGNATION", "date": "2022-09-05", "severity": 6},
        ],
    },
    {
        "ticker": "SFIX",
        "cik": "0001576942",
        "name": "Stitch Fix Inc.",
        "bankruptcy_date": None,  # Not bankrupt yet, but distressed
        "sector": "Retail",
        "signals": [
            {"type": "CEO_DEPARTURE", "date": "2022-06-07", "severity": 7},
            {"type": "MASS_LAYOFFS", "date": "2022-06-23", "severity": 7},
            {"type": "CFO_DEPARTURE", "date": "2023-03-07", "severity": 6},
            {"type": "GOING_CONCERN", "date": "2023-10-03", "severity": 7},
        ],
    },
    {
        "ticker": "PTON",
        "cik": "0001639825",
        "name": "Peloton Interactive Inc.",
        "bankruptcy_date": None,  # Distressed but not bankrupt
        "sector": "Fitness",
        "signals": [
            {"type": "CEO_DEPARTURE", "date": "2022-02-08", "severity": 7},
            {"type": "MASS_LAYOFFS", "date": "2022-02-08", "severity": 8},
            {"type": "CFO_DEPARTURE", "date": "2023-05-04", "severity": 6},
            {"type": "RESTRUCTURING", "date": "2022-08-12", "severity": 7},
            {"type": "GOING_CONCERN", "date": "2024-02-27", "severity": 7},
        ],
    },
]


async def seed_bankruptcy_cases():
    """Seed all known bankruptcy cases into Neo4j."""
    logger.info("Starting bankruptcy case seeding...")

    # Connect to Neo4j
    await neo4j_service.connect()

    for case in BANKRUPTCY_CASES:
        ticker = case["ticker"]
        logger.info(f"Seeding {ticker}: {case['name']}")

        try:
            # Store company
            status = "BANKRUPT" if case.get("bankruptcy_date") else "DISTRESSED"
            await neo4j_service.store_company({
                "ticker": ticker,
                "cik": case["cik"],
                "name": case["name"],
                "status": status,
                "risk_score": 100 if status == "BANKRUPT" else 75,
                "sector": case.get("sector", ""),
            })

            # If bankrupt, add bankruptcy date
            if case.get("bankruptcy_date"):
                await neo4j_service.add_known_bankruptcy(
                    ticker=ticker,
                    cik=case["cik"],
                    name=case["name"],
                    bankruptcy_date=case["bankruptcy_date"],
                    signals=[],
                )

            # Store each signal
            for i, signal in enumerate(case.get("signals", [])):
                # Create a dummy filing for the signal
                filing_accession = f"{ticker}-SEED-{i:04d}"

                # Store filing
                await neo4j_service.store_filing(
                    ticker=ticker,
                    filing_data={
                        "accession_number": filing_accession,
                        "filing_type": "8-K",
                        "filed_at": signal["date"],
                        "url": "",
                    },
                )

                # Store signal
                await neo4j_service.store_signal(
                    ticker=ticker,
                    filing_accession=filing_accession,
                    signal_data={
                        "signal_id": f"{ticker}-{signal['type']}-{signal['date']}",
                        "type": signal["type"],
                        "severity": signal["severity"],
                        "confidence": 0.95,
                        "evidence": f"Seeded signal: {signal['type']}",
                        "date": signal["date"],
                        "item_number": "5.02",
                        "person": None,
                    },
                )

            logger.info(f"  Stored {len(case.get('signals', []))} signals for {ticker}")

        except Exception as e:
            logger.error(f"Error seeding {ticker}: {e}")

    # Close connection
    await neo4j_service.close()
    logger.info("Bankruptcy case seeding complete!")


async def verify_seeded_data():
    """Verify the seeded data is accessible."""
    await neo4j_service.connect()

    for case in BANKRUPTCY_CASES[:3]:
        ticker = case["ticker"]
        signals = await neo4j_service.get_company_signals(ticker)
        logger.info(f"{ticker}: {len(signals)} signals in Neo4j")

    await neo4j_service.close()


if __name__ == "__main__":
    asyncio.run(seed_bankruptcy_cases())
    print("\nVerifying seeded data...")
    asyncio.run(verify_seeded_data())
