"""SEC EDGAR API integration tools with rate limiting."""

import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re

from app.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limiter import sec_edgar_limiter
from app.core.exceptions import SECEdgarError, TickerNotFoundError, RateLimitError

logger = get_logger(__name__)
settings = get_settings()

# SEC EDGAR API endpoints
SEC_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FILING_BASE = "https://www.sec.gov/Archives/edgar/data"


@dataclass
class Filing:
    """Represents an SEC filing."""
    accession_number: str
    filing_type: str
    filed_at: str
    primary_doc: str
    url: str
    items: List[str]  # Item numbers for 8-K


class SECEdgarClient:
    """
    Client for SEC EDGAR API with rate limiting.

    SEC requires no more than 10 requests per second.
    """

    def __init__(self):
        self.headers = {"User-Agent": settings.sec_user_agent}
        self._ticker_to_cik_cache: Dict[str, str] = {}
        self._company_info_cache: Dict[str, Dict[str, Any]] = {}

    def _request(self, url: str, retry_count: int = 3) -> Dict[str, Any]:
        """
        Make a rate-limited request to SEC API.

        Args:
            url: URL to request
            retry_count: Number of retries on failure

        Returns:
            JSON response data

        Raises:
            SECEdgarError: On request failure
            RateLimitError: On rate limit exceeded
        """
        for attempt in range(retry_count):
            # Acquire rate limit token
            wait_time = sec_edgar_limiter.acquire()
            if wait_time > 0:
                logger.debug(f"Rate limited, waited {wait_time:.2f}s")

            try:
                response = requests.get(url, headers=self.headers, timeout=30)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"SEC rate limit hit, retry after {retry_after}s")
                    raise RateLimitError("SEC EDGAR", retry_after)

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"SEC request timeout (attempt {attempt + 1}/{retry_count})")
                if attempt == retry_count - 1:
                    raise SECEdgarError(f"Request timeout for {url}")

            except requests.exceptions.RequestException as e:
                logger.error(f"SEC request error: {e}")
                if attempt == retry_count - 1:
                    raise SECEdgarError(f"Request failed: {e}")

    def _request_html(self, url: str, retry_count: int = 3) -> str:
        """
        Fetch HTML content with rate limiting.

        Args:
            url: URL to fetch
            retry_count: Number of retries

        Returns:
            HTML content

        Raises:
            SECEdgarError: On request failure
        """
        for attempt in range(retry_count):
            sec_edgar_limiter.acquire()

            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                return response.text

            except requests.exceptions.Timeout:
                logger.warning(f"SEC HTML request timeout (attempt {attempt + 1}/{retry_count})")
                if attempt == retry_count - 1:
                    raise SECEdgarError(f"HTML request timeout for {url}")

            except requests.exceptions.RequestException as e:
                logger.error(f"SEC HTML request error: {e}")
                if attempt == retry_count - 1:
                    raise SECEdgarError(f"HTML request failed: {e}")

    def ticker_to_cik(self, ticker: str) -> str:
        """
        Convert ticker symbol to CIK.

        Args:
            ticker: Stock ticker symbol

        Returns:
            CIK (10-digit zero-padded string)

        Raises:
            TickerNotFoundError: If ticker not found
        """
        ticker = ticker.upper().strip()

        if ticker in self._ticker_to_cik_cache:
            return self._ticker_to_cik_cache[ticker]

        try:
            logger.info(f"Looking up CIK for ticker: {ticker}")
            data = self._request(SEC_COMPANY_TICKERS)

            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker:
                    cik = str(entry["cik_str"]).zfill(10)
                    self._ticker_to_cik_cache[ticker] = cik
                    logger.info(f"Found CIK {cik} for {ticker}")
                    return cik

            raise TickerNotFoundError(ticker)

        except (SECEdgarError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error converting ticker to CIK: {e}")
            raise SECEdgarError(f"Failed to lookup ticker: {e}")

    def get_company_info(self, cik: str) -> Dict[str, Any]:
        """
        Get company information from SEC.

        Args:
            cik: Company CIK

        Returns:
            Company info dict with name, sic, tickers, etc.
        """
        cik = cik.zfill(10)

        if cik in self._company_info_cache:
            return self._company_info_cache[cik]

        try:
            url = SEC_SUBMISSIONS.format(cik=cik)
            data = self._request(url)

            info = {
                "cik": cik,
                "name": data.get("name", ""),
                "sic": data.get("sic", ""),
                "sicDescription": data.get("sicDescription", ""),
                "tickers": data.get("tickers", []),
                "exchanges": data.get("exchanges", []),
                "stateOfIncorporation": data.get("stateOfIncorporation", ""),
                "fiscalYearEnd": data.get("fiscalYearEnd", ""),
            }

            self._company_info_cache[cik] = info
            logger.info(f"Got company info for {info['name']} ({cik})")
            return info

        except (SECEdgarError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error getting company info: {e}")
            return {"cik": cik, "name": "", "error": str(e)}

    def get_filings(
        self,
        cik: str,
        filing_types: List[str] = None,
        months_back: int = 24,
    ) -> List[Filing]:
        """
        Get filings for a company.

        Args:
            cik: Company CIK
            filing_types: List of filing types to fetch (default: 8-K, 10-K, 10-Q)
            months_back: How many months of filings to retrieve

        Returns:
            List of Filing objects
        """
        if filing_types is None:
            filing_types = ["8-K", "10-K", "10-Q"]

        cik = cik.zfill(10)

        try:
            url = SEC_SUBMISSIONS.format(cik=cik)
            data = self._request(url)

            filings = []
            recent_filings = data.get("filings", {}).get("recent", {})

            if not recent_filings:
                logger.warning(f"No recent filings found for CIK {cik}")
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

            logger.info(f"Found {len(filings)} filings for CIK {cik}")
            return filings

        except (SECEdgarError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error getting filings: {e}")
            raise SECEdgarError(f"Failed to get filings: {e}")

    def download_filing(self, filing: Filing) -> Dict[str, Any]:
        """
        Download and parse a filing's content.

        Args:
            filing: Filing object

        Returns:
            Dict with filing content and parsed sections
        """
        try:
            logger.debug(f"Downloading filing {filing.accession_number}")
            html = self._request_html(filing.url)
            soup = BeautifulSoup(html, "lxml")

            # Remove scripts and styles
            for tag in soup(["script", "style"]):
                tag.decompose()

            # Extract text content
            text = soup.get_text(separator="\n", strip=True)

            # Limit text size to prevent memory issues
            max_chars = 500000  # ~125k tokens
            if len(text) > max_chars:
                logger.warning(f"Filing {filing.accession_number} truncated from {len(text)} to {max_chars} chars")
                text = text[:max_chars]

            # Parse into sections for 8-K
            sections = {}
            if filing.filing_type == "8-K":
                sections = self._parse_8k_sections(text)

            return {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filed_at": filing.filed_at,
                "items": filing.items,
                "url": filing.url,
                "raw_text": text,
                "sections": sections,
                "char_count": len(text),
            }

        except (SECEdgarError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error downloading filing {filing.accession_number}: {e}")
            return {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filed_at": filing.filed_at,
                "error": str(e),
            }

    def _parse_8k_sections(self, text: str) -> Dict[str, str]:
        """
        Parse 8-K text into item sections.

        Args:
            text: Raw filing text

        Returns:
            Dict mapping item numbers to section content
        """
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

        # Deduplicate markers at same position
        seen_positions = set()
        unique_markers = []
        for pos, item in markers:
            if pos not in seen_positions:
                seen_positions.add(pos)
                unique_markers.append((pos, item))

        # Sort by position
        unique_markers.sort(key=lambda x: x[0])

        # Extract text between markers
        for i, (pos, item) in enumerate(unique_markers):
            if i < len(unique_markers) - 1:
                next_pos = unique_markers[i + 1][0]
                content = text[pos:next_pos]
            else:
                # Last item - take until end or signature
                content = text[pos:]
                sig_match = re.search(r"SIGNATURE", content, re.IGNORECASE)
                if sig_match:
                    content = content[: sig_match.start()]

            # Only keep sections with meaningful content
            if len(content.strip()) > 100:
                sections[item] = content.strip()

        return sections


# Singleton instance
edgar_client = SECEdgarClient()
