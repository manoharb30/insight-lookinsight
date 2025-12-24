"""SEC EDGAR API integration tools with rate limiting.

Implements edgar-crawler approach for reliable document extraction:
- Parses filing index page to find correct document (not XBRL)
- Handles iXBRL URL transformation
- Rate limiting with SEC traffic detection
"""

import requests
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
import warnings

# Suppress BeautifulSoup XML warning
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

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
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# SEC rate limit detection message
SEC_RATE_LIMIT_MESSAGE = "will be managed until action is taken to declare your traffic"

# Item definitions for extraction (based on edgar-crawler)
# Key items for distress signal detection
ITEMS_10K = {
    "1A": "Risk Factors",
    "7": "Management's Discussion and Analysis",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9A": "Controls and Procedures",
}

ITEMS_10Q = {
    "1A": "Risk Factors",
    "2": "Management's Discussion and Analysis",
    "4": "Controls and Procedures",
}

ITEMS_8K = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting",
    "5.02": "Departure of Directors or Certain Officers",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
}

# Regex patterns for item headers
# Matches "ITEM 1A." or "ITEM 7." followed by title
# We look for ITEM + number + optional letter + punctuation
ITEM_HEADER_PATTERN = re.compile(
    r"ITEM\s+(\d+[A-Z]?)\s*[.:\-–—]\s*([A-Z][^0-9\n]{10,})",
    re.IGNORECASE
)


@dataclass
class Filing:
    """Represents an SEC filing."""
    accession_number: str
    filing_type: str
    filed_at: str
    primary_doc: str
    url: str
    items: List[str]  # Item numbers for 8-K
    cik: str = ""  # Company CIK for index page lookup


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

    def _request_html(self, url: str, retry_count: int = 5) -> str:
        """
        Fetch HTML content with rate limiting and SEC traffic detection.

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

                # Check for SEC rate limit message
                if SEC_RATE_LIMIT_MESSAGE in response.text:
                    wait_time = (attempt + 1) * 2  # Exponential backoff: 2, 4, 6, 8, 10 seconds
                    logger.warning(f"SEC rate limit detected, waiting {wait_time}s (attempt {attempt + 1}/{retry_count})")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.text

            except requests.exceptions.Timeout:
                logger.warning(f"SEC HTML request timeout (attempt {attempt + 1}/{retry_count})")
                if attempt == retry_count - 1:
                    raise SECEdgarError(f"HTML request timeout for {url}")
                time.sleep((attempt + 1) * 0.5)

            except requests.exceptions.RequestException as e:
                logger.error(f"SEC HTML request error: {e}")
                if attempt == retry_count - 1:
                    raise SECEdgarError(f"HTML request failed: {e}")
                time.sleep((attempt + 1) * 0.5)

        raise SECEdgarError(f"Failed to fetch {url} after {retry_count} attempts")

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

    def get_filing_index_url(self, cik: str, accession_number: str) -> str:
        """
        Construct the HTML index URL for a filing.

        The index page lists all documents in the filing, allowing us to
        find the correct narrative document (not XBRL).

        Args:
            cik: Company CIK (with or without leading zeros)
            accession_number: Filing accession number (e.g., "0001104659-25-019858")

        Returns:
            URL to the filing index page

        Example:
            https://www.sec.gov/Archives/edgar/data/1093691/000110465925019858/0001104659-25-019858-index.html
        """
        cik_clean = cik.lstrip('0')
        acc_clean = accession_number.replace('-', '')
        # Index URL format: {accession-number-with-dashes}-index.html
        return f"{SEC_ARCHIVES_BASE}/{cik_clean}/{acc_clean}/{accession_number}-index.html"

    def find_filing_document_url(
        self,
        index_url: str,
        filing_type: str,
    ) -> Optional[str]:
        """
        Parse the filing index page and find the correct document URL.

        This is the key improvement from edgar-crawler: instead of trusting
        the primaryDocument field (which may point to XBRL), we parse the
        index page and find the document where Type matches the filing type.

        Args:
            index_url: URL to the filing index page
            filing_type: Filing type to match (e.g., "8-K", "10-K")

        Returns:
            URL to the correct document, or None if not found
        """
        try:
            html = self._request_html(index_url)
            soup = BeautifulSoup(html, "lxml")

            # Find the "Document Format Files" table
            for table in soup.find_all("table"):
                summary = table.attrs.get("summary", "")
                if summary == "Document Format Files":
                    # Skip header row, iterate through data rows
                    rows = table.find_all("tr")
                    for tr in rows[1:]:
                        cols = tr.find_all("td")
                        if len(cols) >= 4:
                            # Column layout: Seq, Description, Document, Type, Size
                            # Type is typically in column index 3
                            doc_type = cols[3].get_text(strip=True)

                            # Match the filing type
                            if doc_type == filing_type:
                                # Document link is in column 2
                                link_tag = cols[2].find("a")
                                if link_tag and link_tag.get("href"):
                                    href = link_tag["href"]

                                    # Prefer .htm/.html files
                                    if href.endswith((".htm", ".html")):
                                        full_url = "https://www.sec.gov" + href

                                        # Handle iXBRL viewer URLs
                                        # These have format: /ix?doc=/Archives/...
                                        # We need to strip the /ix?doc= prefix
                                        if "ix?doc=/" in full_url:
                                            full_url = full_url.replace("ix?doc=/", "")
                                            logger.debug(f"Transformed iXBRL URL: {full_url}")

                                        logger.info(f"Found document for {filing_type}: {href}")
                                        return full_url

                    # If no .htm/.html found, look for complete submission text file
                    for tr in rows[1:]:
                        cols = tr.find_all("td")
                        if len(cols) >= 2:
                            desc = cols[1].get_text(strip=True)
                            if "Complete submission text file" in desc:
                                link_tag = cols[2].find("a")
                                if link_tag and link_tag.get("href"):
                                    href = link_tag["href"]
                                    full_url = "https://www.sec.gov" + href
                                    logger.info(f"Using complete submission file: {href}")
                                    return full_url

            logger.warning(f"Could not find document for {filing_type} in index: {index_url}")
            return None

        except Exception as e:
            logger.error(f"Error parsing filing index {index_url}: {e}")
            return None

    def find_exhibit_urls(self, index_url: str) -> List[Dict[str, str]]:
        """
        Find exhibit URLs (EX-99.x) in a filing's index page.

        8-K filings often have press releases in EX-99.1 exhibits that contain
        the actual signal content (restructuring announcements, layoffs, etc.).

        Args:
            index_url: URL to the filing index page

        Returns:
            List of {type, url} for each exhibit found
        """
        exhibits = []
        try:
            html = self._request_html(index_url)
            soup = BeautifulSoup(html, "lxml")

            for table in soup.find_all("table"):
                summary = table.attrs.get("summary", "")
                if summary == "Document Format Files":
                    rows = table.find_all("tr")
                    for tr in rows[1:]:
                        cols = tr.find_all("td")
                        if len(cols) >= 4:
                            doc_type = cols[3].get_text(strip=True)

                            # Look for EX-99.x exhibits (press releases, etc.)
                            if doc_type.startswith("EX-99"):
                                link_tag = cols[2].find("a")
                                if link_tag and link_tag.get("href"):
                                    href = link_tag["href"]
                                    if href.endswith((".htm", ".html", ".txt")):
                                        full_url = "https://www.sec.gov" + href
                                        exhibits.append({
                                            "type": doc_type,
                                            "url": full_url,
                                        })
                                        logger.debug(f"Found exhibit {doc_type}: {href}")

            return exhibits

        except Exception as e:
            logger.error(f"Error finding exhibits in {index_url}: {e}")
            return []

    def download_exhibit(self, exhibit_url: str) -> str:
        """
        Download and extract text from an exhibit.

        Args:
            exhibit_url: URL to the exhibit

        Returns:
            Extracted text from the exhibit
        """
        try:
            html = self._request_html(exhibit_url)
            return self._extract_text_from_html(html)
        except Exception as e:
            logger.error(f"Error downloading exhibit {exhibit_url}: {e}")
            return ""

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
            filing_types = ["8-K", "10-K"]  # Include 10-K for going concern detection

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
                        cik=cik,  # Include CIK for index page lookup
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
        Download filing content using index page approach.

        This uses the edgar-crawler strategy:
        1. Parse the filing's index page to find all documents
        2. Find the document where Type matches the filing type
        3. Handle iXBRL URL transformation
        4. Fall back to primary document URL if needed

        Args:
            filing: Filing object

        Returns:
            Dict with filing content
        """
        try:
            logger.debug(f"Downloading filing {filing.accession_number}")

            # Step 1: Try to find correct document via index page
            doc_url = None
            if filing.cik:
                index_url = self.get_filing_index_url(filing.cik, filing.accession_number)
                doc_url = self.find_filing_document_url(index_url, filing.filing_type)

            # Step 2: Fall back to original URL if index approach fails
            if not doc_url:
                doc_url = filing.url
                logger.debug(f"Using primary document URL: {doc_url}")

            # Step 3: Download the document
            html = self._request_html(doc_url)

            # Step 4: Parse and extract text with structure preservation
            text = self._extract_text_from_html(html)

            # Limit size - 100k chars for full filing
            max_chars = 100000
            if len(text) > max_chars:
                logger.warning(f"Filing {filing.accession_number} truncated from {len(text)} to {max_chars} chars")
                text = text[:max_chars]

            return {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filed_at": filing.filed_at,
                "items": filing.items,
                "url": doc_url,  # Use the actual URL we downloaded from
                "raw_text": text,
                "char_count": len(text),
            }

        except (SECEdgarError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error downloading {filing.accession_number}: {e}")
            return {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filed_at": filing.filed_at,
                "error": str(e),
            }

    def _extract_text_from_html(self, html: str) -> str:
        """
        Extract text from HTML/iXBRL while preserving document structure.

        Based on edgar-crawler's approach:
        - Add newlines after block elements (div, tr, p, li)
        - Add newlines for <br> tags
        - Add spaces around th/td elements
        - Remove scripts, styles, and hidden elements
        - Handle iXBRL by removing hidden XBRL metadata sections

        Args:
            html: Raw HTML content (may be iXBRL)

        Returns:
            Cleaned text with preserved structure
        """
        # Add newlines after block elements to preserve structure
        html = re.sub(r"(<\s*/\s*(div|tr|p|li)\s*>)", r"\1\n\n", html, flags=re.IGNORECASE)
        html = re.sub(r"(<br\s*/?>)", r"\1\n\n", html, flags=re.IGNORECASE)
        html = re.sub(r"(<\s*/\s*(th|td)\s*>)", r" \1 ", html, flags=re.IGNORECASE)

        soup = BeautifulSoup(html, "lxml")

        # Remove scripts, styles, and other non-content elements
        for tag in soup(["script", "style", "meta", "link", "noscript"]):
            tag.decompose()

        # Remove hidden iXBRL elements (contain XBRL metadata, not narrative)
        # These have display:none and contain ix:hidden, ix:header, etc.
        for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.IGNORECASE)):
            tag.decompose()

        # Remove ix:hidden elements directly (iXBRL hidden metadata)
        for tag in soup.find_all(["ix:hidden", "ix:header", "ix:references", "ix:resources"]):
            tag.decompose()

        # Also try with namespace prefix variations
        for tag in soup.find_all(re.compile(r"^ix:", re.IGNORECASE)):
            # Keep ix:nonfraction and ix:nonnumeric - these contain visible numbers
            # But remove metadata containers
            tag_name = tag.name.lower() if tag.name else ""
            if tag_name in ["ix:hidden", "ix:header", "ix:references", "ix:resources"]:
                tag.decompose()

        # Extract text
        text = soup.get_text(separator=" ", strip=True)

        # Clean up the text
        text = self._clean_extracted_text(text)

        return text

    def _clean_extracted_text(self, text: str) -> str:
        """
        Clean extracted text by fixing common issues.

        Based on edgar-crawler's clean_text approach.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        # Fix broken headers like "I T E M  5.02" -> "ITEM 5.02"
        text = re.sub(
            r"(I\s*T\s*E\s*M)(\s+)(\d)",
            r"ITEM\2\3",
            text,
            flags=re.IGNORECASE
        )

        # Remove Table of Contents and similar headers
        text = re.sub(
            r"(TABLE\s+OF\s+CONTENTS|INDEX\s+TO\s+FINANCIAL\s+STATEMENTS|BACK\s+TO\s+CONTENTS)",
            "",
            text,
            flags=re.IGNORECASE
        )

        # Remove page numbers (standalone numbers on lines)
        text = re.sub(r"\n\s*[-–—]*\d+[-–—]*\s*\n", "\n", text)
        text = re.sub(r"\n\s*Page\s+\d+\s*\n", "\n", text, flags=re.IGNORECASE)

        # Normalize special characters
        text = re.sub(r"[\xa0\u200b\u2009]", " ", text)  # Various spaces
        text = re.sub(r"[\u2018\u2019\x91\x92]", "'", text)  # Smart single quotes
        text = re.sub(r"[\u201c\u201d\x93\x94]", '"', text)  # Smart double quotes
        text = re.sub(r"[\u2010-\u2015\x96\x97]", "-", text)  # Various dashes

        # Remove multiple consecutive blank lines
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        # Remove multiple consecutive spaces
        text = re.sub(r"[ ]{2,}", " ", text)

        return text.strip()

    def extract_items(
        self,
        text: str,
        filing_type: str,
        target_items: List[str] = None,
    ) -> Dict[str, str]:
        """
        Extract specific items from filing text using regex patterns.

        Based on edgar-crawler's extract_items approach - finds ITEM X.XX headers
        and extracts text between them.

        Args:
            text: Full filing text
            filing_type: Filing type (10-K, 10-Q, 8-K)
            target_items: List of item numbers to extract (e.g., ["1A", "7"])
                          If None, extracts all relevant items for filing type

        Returns:
            Dict mapping item number to extracted text
        """
        # Get item definitions for this filing type
        if filing_type == "10-K":
            item_defs = ITEMS_10K
        elif filing_type == "10-Q":
            item_defs = ITEMS_10Q
        elif filing_type == "8-K":
            item_defs = ITEMS_8K
        else:
            item_defs = {}

        # Default to extracting key items for distress detection
        if target_items is None:
            if filing_type == "10-K":
                target_items = ["1A", "7", "8", "9A"]  # Risk Factors, MD&A, Financials, Controls
            elif filing_type == "10-Q":
                target_items = ["1A", "2", "4"]
            elif filing_type == "8-K":
                target_items = ["2.04", "2.05", "2.06", "5.02", "8.01"]
            else:
                return {}

        extracted = {}

        # Find all ITEM headers and their positions
        item_positions = []
        for match in ITEM_HEADER_PATTERN.finditer(text):
            item_num = match.group(1).upper()
            # Normalize: "1.A" -> "1A", "7.01" -> "7.01"
            item_num = item_num.replace(".", "") if item_num.endswith(("A", "B")) else item_num
            item_positions.append({
                "item": item_num,
                "start": match.start(),
                "end": match.end(),
                "title": match.group(2).strip() if match.lastindex >= 2 else "",
            })

        logger.debug(f"Found {len(item_positions)} ITEM headers in {filing_type}")

        # Filter out TOC entries - keep only headers that are followed by substantial content
        # TOC entries are typically followed immediately by another ITEM header or page number
        filtered_positions = []
        for i, pos in enumerate(item_positions):
            # Check if next header is more than 1000 chars away (real content)
            if i + 1 < len(item_positions):
                gap = item_positions[i + 1]["start"] - pos["end"]
            else:
                gap = len(text) - pos["end"]

            # Only keep if there's substantial content after this header
            if gap > 1000:
                filtered_positions.append(pos)

        logger.debug(f"After filtering TOC entries: {len(filtered_positions)} actual items")
        item_positions = filtered_positions

        # Extract text for each target item
        for target in target_items:
            target_upper = target.upper()

            # Find the start position of this item
            item_start = None
            item_end = None

            for i, pos in enumerate(item_positions):
                if pos["item"] == target_upper:
                    item_start = pos["end"]

                    # End is the start of the next item, or end of document
                    if i + 1 < len(item_positions):
                        item_end = item_positions[i + 1]["start"]
                    else:
                        item_end = len(text)
                    break

            if item_start is not None:
                item_text = text[item_start:item_end].strip()

                # Skip if too short (likely just a reference/TOC entry)
                if len(item_text) > 500:
                    # Limit individual item to 50k chars
                    if len(item_text) > 50000:
                        item_text = item_text[:50000] + "\n... [truncated]"

                    extracted[target_upper] = item_text
                    logger.debug(f"Extracted Item {target}: {len(item_text)} chars")
                else:
                    logger.debug(f"Item {target} too short ({len(item_text)} chars), skipping")

        return extracted

    def download_filing_with_items(
        self,
        filing: Filing,
        extract_items: bool = True,
    ) -> Dict[str, Any]:
        """
        Download filing and optionally extract specific items.

        For 10-K/10-Q, extracts key items (Risk Factors, MD&A, Controls).
        For 8-K, returns the full text (typically shorter).

        Args:
            filing: Filing object
            extract_items: Whether to extract items (True) or return full text

        Returns:
            Dict with filing content and extracted items
        """
        try:
            logger.debug(f"Downloading filing {filing.accession_number}")

            # Step 1: Find correct document via index page
            doc_url = None
            if filing.cik:
                index_url = self.get_filing_index_url(filing.cik, filing.accession_number)
                doc_url = self.find_filing_document_url(index_url, filing.filing_type)

            # Step 2: Fall back to original URL if index approach fails
            if not doc_url:
                doc_url = filing.url
                logger.debug(f"Using primary document URL: {doc_url}")

            # Step 3: Download the document
            html = self._request_html(doc_url)

            # Step 4: Extract full text
            full_text = self._extract_text_from_html(html)

            result = {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filed_at": filing.filed_at,
                "items": filing.items,
                "url": doc_url,
                "char_count": len(full_text),
            }

            # Step 5: Extract items for 10-K/10-Q, or return full text for 8-K
            if extract_items and filing.filing_type in ["10-K", "10-Q"]:
                items_extracted = self.extract_items(full_text, filing.filing_type)

                if items_extracted:
                    # Combine extracted items for LLM analysis
                    combined_text = []
                    for item_num, item_text in items_extracted.items():
                        item_name = ITEMS_10K.get(item_num, "") or ITEMS_10Q.get(item_num, "")
                        combined_text.append(f"\n\n{'='*60}\nITEM {item_num}: {item_name}\n{'='*60}\n\n{item_text}")

                    result["raw_text"] = "".join(combined_text)
                    result["extracted_items"] = list(items_extracted.keys())
                    logger.info(f"Extracted items {list(items_extracted.keys())} from {filing.filing_type}")
                else:
                    # Fallback: couldn't extract items, use truncated full text
                    logger.warning(f"Could not extract items from {filing.accession_number}, using truncated text")
                    max_chars = 150000  # Increased limit
                    if len(full_text) > max_chars:
                        full_text = full_text[:max_chars] + "\n... [truncated]"
                    result["raw_text"] = full_text
                    result["extracted_items"] = []
            else:
                # 8-K filings: include main body + exhibits
                combined_parts = [full_text]

                # Download EX-99.x exhibits (press releases with actual signal content)
                if filing.cik:
                    index_url = self.get_filing_index_url(filing.cik, filing.accession_number)
                    exhibits = self.find_exhibit_urls(index_url)

                    for exhibit in exhibits[:3]:  # Limit to first 3 exhibits
                        exhibit_text = self.download_exhibit(exhibit["url"])
                        if exhibit_text and len(exhibit_text) > 100:
                            combined_parts.append(
                                f"\n\n{'='*60}\n{exhibit['type']}: EXHIBIT/PRESS RELEASE\n{'='*60}\n\n{exhibit_text}"
                            )
                            logger.debug(f"Added exhibit {exhibit['type']}: {len(exhibit_text)} chars")

                    if len(exhibits) > 0:
                        result["exhibits_included"] = [e["type"] for e in exhibits[:3]]

                # Combine and truncate
                combined_text = "\n\n".join(combined_parts)
                max_chars = 100000
                if len(combined_text) > max_chars:
                    combined_text = combined_text[:max_chars] + "\n... [truncated]"

                result["raw_text"] = combined_text
                result["char_count"] = len(combined_text)

            return result

        except (SECEdgarError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error downloading {filing.accession_number}: {e}")
            return {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filed_at": filing.filed_at,
                "error": str(e),
            }


# Singleton instance
edgar_client = SECEdgarClient()
