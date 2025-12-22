"""SEC EDGAR API integration tools."""

import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
import re

from app.config import get_settings

settings = get_settings()

# SEC EDGAR API endpoints
SEC_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FILING_BASE = "https://www.sec.gov/Archives/edgar/data"


@dataclass
class Filing:
    accession_number: str
    filing_type: str
    filed_at: str
    primary_doc: str
    url: str
    items: List[str]  # Item numbers for 8-K


class SECEdgarClient:
    """Client for SEC EDGAR API."""

    def __init__(self):
        self.headers = {"User-Agent": settings.sec_user_agent}
        self._ticker_to_cik_cache: Dict[str, str] = {}

    def _request(self, url: str) -> Dict[str, Any]:
        """Make a request to SEC API with rate limiting."""
        time.sleep(0.1)  # SEC requires 10 requests per second max
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _request_html(self, url: str) -> str:
        """Fetch HTML content."""
        time.sleep(0.1)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.text

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Convert ticker symbol to CIK."""
        ticker = ticker.upper()

        if ticker in self._ticker_to_cik_cache:
            return self._ticker_to_cik_cache[ticker]

        try:
            data = self._request(SEC_COMPANY_TICKERS)
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker:
                    cik = str(entry["cik_str"]).zfill(10)
                    self._ticker_to_cik_cache[ticker] = cik
                    return cik
            return None
        except Exception as e:
            print(f"Error converting ticker to CIK: {e}")
            return None

    def get_company_info(self, cik: str) -> Dict[str, Any]:
        """Get company information from SEC."""
        try:
            url = SEC_SUBMISSIONS.format(cik=cik.zfill(10))
            data = self._request(url)
            return {
                "cik": cik,
                "name": data.get("name", ""),
                "sic": data.get("sic", ""),
                "sicDescription": data.get("sicDescription", ""),
                "tickers": data.get("tickers", []),
                "exchanges": data.get("exchanges", []),
            }
        except Exception as e:
            print(f"Error getting company info: {e}")
            return {"cik": cik, "name": "", "error": str(e)}

    def get_filings(
        self,
        cik: str,
        filing_types: List[str] = ["8-K", "10-K", "10-Q"],
        months_back: int = 24,
    ) -> List[Filing]:
        """Get filings for a company."""
        try:
            url = SEC_SUBMISSIONS.format(cik=cik.zfill(10))
            data = self._request(url)

            filings = []
            recent_filings = data.get("filings", {}).get("recent", {})

            if not recent_filings:
                return filings

            cutoff_date = datetime.now() - timedelta(days=months_back * 30)

            accession_numbers = recent_filings.get("accessionNumber", [])
            forms = recent_filings.get("form", [])
            filing_dates = recent_filings.get("filingDate", [])
            primary_docs = recent_filings.get("primaryDocument", [])
            items = recent_filings.get("items", [])

            for i, (acc, form, date, doc) in enumerate(
                zip(accession_numbers, forms, filing_dates, primary_docs)
            ):
                if form not in filing_types:
                    continue

                try:
                    filing_date = datetime.strptime(date, "%Y-%m-%d")
                    if filing_date < cutoff_date:
                        continue
                except ValueError:
                    continue

                # Format accession number for URL
                acc_formatted = acc.replace("-", "")
                url = f"{SEC_FILING_BASE}/{cik.lstrip('0')}/{acc_formatted}/{doc}"

                # Get items for 8-K filings
                filing_items = []
                if form == "8-K" and i < len(items):
                    item_str = items[i] if items[i] else ""
                    filing_items = [x.strip() for x in item_str.split(",") if x.strip()]

                filings.append(
                    Filing(
                        accession_number=acc,
                        filing_type=form,
                        filed_at=date,
                        primary_doc=doc,
                        url=url,
                        items=filing_items,
                    )
                )

            return filings

        except Exception as e:
            print(f"Error getting filings: {e}")
            return []

    def download_filing(self, filing: Filing) -> Dict[str, Any]:
        """Download and parse a filing's content."""
        try:
            html = self._request_html(filing.url)
            soup = BeautifulSoup(html, "lxml")

            # Remove scripts and styles
            for tag in soup(["script", "style"]):
                tag.decompose()

            # Extract text content
            text = soup.get_text(separator="\n", strip=True)

            # Parse into sections for 8-K
            sections = self._parse_8k_sections(text) if filing.filing_type == "8-K" else {}

            return {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filed_at": filing.filed_at,
                "items": filing.items,
                "url": filing.url,
                "raw_text": text,
                "sections": sections,
            }

        except Exception as e:
            print(f"Error downloading filing {filing.accession_number}: {e}")
            return {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "error": str(e),
            }

    def _parse_8k_sections(self, text: str) -> Dict[str, str]:
        """Parse 8-K text into item sections."""
        sections = {}

        # Common 8-K item patterns
        item_patterns = [
            r"Item\s*(\d+\.\d+)",
            r"ITEM\s*(\d+\.\d+)",
        ]

        # Find all item markers
        markers = []
        for pattern in item_patterns:
            for match in re.finditer(pattern, text):
                markers.append((match.start(), match.group(1)))

        # Sort by position
        markers.sort(key=lambda x: x[0])

        # Extract text between markers
        for i, (pos, item) in enumerate(markers):
            if i < len(markers) - 1:
                next_pos = markers[i + 1][0]
                content = text[pos:next_pos]
            else:
                # Last item - take until end or signature
                content = text[pos:]
                sig_match = re.search(r"SIGNATURE", content, re.IGNORECASE)
                if sig_match:
                    content = content[: sig_match.start()]

            sections[item] = content.strip()

        return sections


# Singleton instance
edgar_client = SECEdgarClient()
