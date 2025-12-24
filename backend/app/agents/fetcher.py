"""Agent 1: Filing Fetcher - SEC EDGAR integration."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.tools.edgar import edgar_client, Filing


@dataclass
class FetchResult:
    ticker: str
    cik: str
    company_name: str
    filings: List[Dict[str, Any]]
    total_filings: int
    filings_by_type: Dict[str, int]
    error: Optional[str] = None


class FilingFetcherAgent:
    """
    Agent 1: SEC Filing Retrieval Specialist

    Only fetches 8-K (discrete events) and 10-K (going concern).
    10-Q excluded - just noise that repeats 8-K content.
    """

    def __init__(self):
        self.role = "SEC Filing Retrieval Specialist"
        self.goal = "Fetch 8-K and 10-K filings for bankruptcy signal analysis"

    async def run(
        self,
        ticker: str,
        months_back: int = 36,
        filing_types: List[str] = ["8-K", "10-K"],  # NO 10-Q
        update_callback=None,
    ) -> FetchResult:
        """
        Fetch SEC filings for a given ticker.

        Only 8-K and 10-K - no 10-Q (noise).
        """
        ticker = ticker.upper().strip()

        # Step 1: Convert ticker to CIK
        if update_callback:
            await update_callback("Converting ticker to CIK...")

        cik = edgar_client.ticker_to_cik(ticker)
        if not cik:
            return FetchResult(
                ticker=ticker,
                cik="",
                company_name="",
                filings=[],
                total_filings=0,
                filings_by_type={},
                error=f"Could not find CIK for ticker {ticker}",
            )

        # Step 2: Get company info
        if update_callback:
            await update_callback("Fetching company information...")

        company_info = edgar_client.get_company_info(cik)
        company_name = company_info.get("name", "")

        # Step 3: Get filing list
        if update_callback:
            await update_callback("Retrieving filing list...")

        filings = edgar_client.get_filings(
            cik=cik,
            filing_types=filing_types,
            months_back=months_back,
        )

        if update_callback:
            await update_callback(f"Found {len(filings)} filings (8-K + 10-K only)")

        # Step 4: Download filing content
        downloaded_filings = []
        filings_by_type = {"8-K": 0, "10-K": 0}

        for i, filing in enumerate(filings):
            if update_callback and i % 5 == 0:
                await update_callback(
                    f"Downloading filing {i + 1}/{len(filings)}..."
                )

            filing_data = edgar_client.download_filing(filing)
            if "error" not in filing_data:
                downloaded_filings.append(filing_data)
                filing_type = filing_data.get("filing_type", "")
                if filing_type in filings_by_type:
                    filings_by_type[filing_type] += 1

        if update_callback:
            await update_callback(
                f"Downloaded {len(downloaded_filings)} filings "
                f"({filings_by_type.get('8-K', 0)} 8-K, {filings_by_type.get('10-K', 0)} 10-K)"
            )

        return FetchResult(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            filings=downloaded_filings,
            total_filings=len(downloaded_filings),
            filings_by_type=filings_by_type,
        )


# Singleton instance
fetcher_agent = FilingFetcherAgent()
