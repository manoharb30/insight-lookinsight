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
    error: Optional[str] = None


class FilingFetcherAgent:
    """
    Agent 1: SEC Filing Retrieval Specialist

    Role: Retrieve SEC filings from EDGAR API
    Goal: Fetch all relevant SEC filings for bankruptcy signal analysis
    """

    def __init__(self):
        self.role = "SEC Filing Retrieval Specialist"
        self.goal = "Fetch all relevant SEC filings for bankruptcy signal analysis"
        self.backstory = "Expert in navigating SEC EDGAR database and retrieving corporate filings"

    async def run(
        self,
        ticker: str,
        months_back: int = 24,
        filing_types: List[str] = ["8-K", "10-K", "10-Q"],
        update_callback=None,
    ) -> FetchResult:
        """
        Fetch SEC filings for a given ticker.

        Args:
            ticker: Stock ticker symbol
            months_back: How many months of filings to fetch
            filing_types: Types of filings to fetch
            update_callback: Optional callback for progress updates
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
            await update_callback(f"Found {len(filings)} filings")

        # Step 4: Download filing content
        downloaded_filings = []
        for i, filing in enumerate(filings):
            if update_callback and i % 5 == 0:
                await update_callback(
                    f"Downloading filing {i + 1}/{len(filings)}..."
                )

            filing_data = edgar_client.download_filing(filing)
            if "error" not in filing_data:
                downloaded_filings.append(filing_data)

        if update_callback:
            await update_callback(
                f"Downloaded {len(downloaded_filings)} filings successfully"
            )

        return FetchResult(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            filings=downloaded_filings,
            total_filings=len(downloaded_filings),
        )


# Singleton instance
fetcher_agent = FilingFetcherAgent()
