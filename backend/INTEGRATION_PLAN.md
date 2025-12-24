# Edgar-Crawler Integration Plan

## Overview

This plan integrates key improvements from the [edgar-crawler](https://github.com/lefterisloukas/edgar-crawler) project to fix our SEC filing extraction issues.

**Current Problems:**
1. Wrong document downloaded (XBRL instead of narrative)
2. No item-by-item extraction (LLM gets raw blob)
3. Poor text cleaning (broken headers, table noise)
4. No rate limit handling

---

## Phase 1: Fix Document Download

**Problem:** We trust `primaryDocument` from SEC API, which sometimes points to XBRL files instead of the narrative document.

**Solution:** Parse the filing's HTML index page and find the correct document by matching the filing type.

### Files to Modify
- `app/tools/edgar.py`

### Changes

#### 1.1 Add function to get HTML index URL

```python
def get_filing_index_url(self, cik: str, accession_number: str) -> str:
    """
    Construct the HTML index URL for a filing.

    Example: https://www.sec.gov/Archives/edgar/data/1093691/000110465925019858/-index.html
    """
    cik_clean = cik.lstrip('0')
    acc_clean = accession_number.replace('-', '')
    return f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/-index.html"
```

#### 1.2 Add function to find correct document in index

```python
def find_filing_document(self, index_url: str, filing_type: str) -> Optional[str]:
    """
    Parse the filing index page and find the correct document URL.

    Looks in the 'Document Format Files' table for a row where
    Type matches the filing_type (e.g., '8-K') and prefers .htm/.html files.
    """
    html = self._request_html(index_url)
    soup = BeautifulSoup(html, "lxml")

    for table in soup.find_all("table"):
        summary = table.attrs.get("summary", "")
        if summary == "Document Format Files":
            for tr in table.find_all("tr")[1:]:  # Skip header row
                cols = tr.find_all("td")
                if len(cols) >= 4:
                    doc_type = cols[3].get_text(strip=True)  # Type column

                    if doc_type == filing_type:
                        link_tag = cols[2].find("a")  # Document column
                        if link_tag and link_tag.get("href"):
                            href = link_tag["href"]
                            # Prefer .htm/.html files
                            if href.endswith((".htm", ".html")):
                                full_url = "https://www.sec.gov" + href
                                # Handle iXBRL viewer URLs
                                if "ix?doc=/" in full_url:
                                    full_url = full_url.replace("ix?doc=/", "")
                                return full_url

    return None
```

#### 1.3 Modify download_filing to use new approach

```python
def download_filing(self, filing: Filing) -> Dict[str, Any]:
    """
    Download filing content using index page approach.
    """
    try:
        # Step 1: Get the index page URL
        index_url = self.get_filing_index_url(
            cik=filing.accession_number.split('-')[0],  # Extract CIK
            accession_number=filing.accession_number
        )

        # Step 2: Find the correct document
        doc_url = self.find_filing_document(index_url, filing.filing_type)

        if not doc_url:
            # Fallback to original URL
            doc_url = filing.url
            logger.warning(f"Could not find document in index, using primary: {doc_url}")

        # Step 3: Download the document
        html = self._request_html(doc_url)

        # ... rest of processing
```

---

## Phase 2: Item-by-Item Extraction

**Problem:** We send entire filing text to LLM. It's noisy and often contains XBRL garbage.

**Solution:** Extract individual items (1.01, 2.05, 5.02, etc.) using regex patterns before sending to LLM.

### Files to Create/Modify
- `app/tools/item_extractor.py` (NEW)
- `app/tools/extraction.py` (MODIFY)

### Changes

#### 2.1 Create item_extractor.py

```python
"""SEC filing item extraction using regex patterns."""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass

# 8-K item lists
ITEM_LIST_8K = [
    "1.01", "1.02", "1.03", "1.04", "1.05",
    "2.01", "2.02", "2.03", "2.04", "2.05", "2.06",
    "3.01", "3.02", "3.03",
    "4.01", "4.02",
    "5.01", "5.02", "5.03", "5.04", "5.05", "5.06", "5.07", "5.08",
    "6.01", "6.02", "6.03", "6.04", "6.05",
    "7.01", "8.01", "9.01",
    "SIGNATURE",
]

# Pre-Aug 2004 format
ITEM_LIST_8K_OBSOLETE = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    "SIGNATURE",
]

OBSOLETE_CUTOFF_DATE = "2004-08-23"

# Regex flags
REGEX_FLAGS = re.IGNORECASE | re.DOTALL | re.MULTILINE


@dataclass
class ExtractedItem:
    """Represents an extracted item from a filing."""
    item_number: str
    content: str
    start_pos: int
    end_pos: int


class ItemExtractor:
    """
    Extract individual items from SEC filings using regex patterns.

    Based on edgar-crawler's extract_items.py approach.
    """

    def __init__(self, remove_tables: bool = True):
        self.remove_tables = remove_tables

    def get_item_list(self, filing_type: str, filing_date: str) -> List[str]:
        """Get the appropriate item list based on filing type and date."""
        if filing_type == "8-K":
            if filing_date >= OBSOLETE_CUTOFF_DATE:
                return ITEM_LIST_8K
            else:
                return ITEM_LIST_8K_OBSOLETE
        elif filing_type == "10-K":
            return ["1", "1A", "1B", "2", "3", "4", "5", "6", "7", "7A", "8", "9", "9A", "9B", "10", "11", "12", "13", "14", "15"]
        else:
            return []

    def adjust_item_pattern(self, item_index: str) -> str:
        """
        Create regex pattern for matching item headers.

        Converts "5.02" → pattern matching "ITEM 5.02" or "ITEMS 5.02"
        """
        if item_index == "SIGNATURE":
            return r"SIGNATURE(S|\(S\))?"

        # Escape dots for regex
        escaped = item_index.replace(".", r"\.")

        # Handle letter suffixes (9A, 1B, etc.)
        if "A" in escaped:
            escaped = escaped.replace("A", r"[^\S\r\n]*A")
        elif "B" in escaped:
            escaped = escaped.replace("B", r"[^\S\r\n]*B")

        return rf"ITEMS?\s*{escaped}"

    def parse_item(
        self,
        text: str,
        item_index: str,
        next_items: List[str],
        last_position: int = 0
    ) -> Optional[ExtractedItem]:
        """
        Extract a single item's content from the filing text.

        Finds text between current item header and next item header.
        """
        item_pattern = self.adjust_item_pattern(item_index)

        # Find all occurrences of this item
        matches = list(re.finditer(
            rf"\n[^\S\r\n]*{item_pattern}[.*~\-:\s\(]",
            text,
            flags=REGEX_FLAGS
        ))

        if not matches:
            return None

        # Find the match after last_position (skip ToC mentions)
        best_match = None
        best_content = ""

        for match in matches:
            if match.start() < last_position:
                continue

            offset = match.start()

            # Try to find where this item ends (next item starts)
            for next_item in next_items:
                next_pattern = self.adjust_item_pattern(next_item)

                end_match = re.search(
                    rf"\n[^\S\r\n]*{next_pattern}[.*~\-:\s\(]",
                    text[offset + len(match.group()):],
                    flags=REGEX_FLAGS
                )

                if end_match:
                    content = text[offset:offset + len(match.group()) + end_match.start()]
                    if len(content) > len(best_content):
                        best_match = match
                        best_content = content
                    break

            # If no next item found, take rest of text (last item)
            if not best_match and match.start() >= last_position:
                best_match = match
                best_content = text[offset:]

        if best_match and best_content:
            return ExtractedItem(
                item_number=item_index,
                content=self._clean_item_content(best_content),
                start_pos=best_match.start(),
                end_pos=best_match.start() + len(best_content)
            )

        return None

    def extract_all_items(
        self,
        text: str,
        filing_type: str,
        filing_date: str
    ) -> Dict[str, str]:
        """
        Extract all items from a filing.

        Returns dict like {"item_2.05": "content...", "item_5.02": "content..."}
        """
        items_list = self.get_item_list(filing_type, filing_date)

        if not items_list:
            return {}

        # Clean text first
        text = self.clean_text(text)

        extracted = {}
        last_pos = 0

        for i, item_index in enumerate(items_list):
            next_items = items_list[i + 1:]

            result = self.parse_item(text, item_index, next_items, last_pos)

            if result:
                key = f"item_{item_index}" if item_index != "SIGNATURE" else "signature"
                extracted[key] = result.content
                last_pos = result.end_pos

        return extracted

    def clean_text(self, text: str) -> str:
        """Clean and normalize filing text."""
        # Fix broken headers like "I T E M  5.02"
        text = re.sub(
            r"(\n[^\S\r\n]*)(I[^\S\r\n]*T[^\S\r\n]*E[^\S\r\n]*M)([^\S\r\n]+)(\d)",
            r"\1ITEM\3\4",
            text,
            flags=re.IGNORECASE
        )

        # Remove ToC headers
        text = re.sub(
            r"\n[^\S\r\n]*(TABLE\s+OF\s+CONTENTS|INDEX\s+TO\s+FINANCIAL)[^\S\r\n]*\n",
            "\n",
            text,
            flags=re.IGNORECASE | re.MULTILINE
        )

        # Remove page numbers
        text = re.sub(r"\n[^\S\r\n]*[-–—]*\d+[-–—]*[^\S\r\n]*\n", "\n", text)
        text = re.sub(r"\n[^\S\r\n]*Page\s+\d+[^\S\r\n]*\n", "\n", text, flags=re.IGNORECASE)

        # Normalize special characters
        text = re.sub(r"[\xa0\u200b]", " ", text)  # Non-breaking spaces
        text = re.sub(r"[\u2018\u2019]", "'", text)  # Smart quotes
        text = re.sub(r"[\u201c\u201d]", '"', text)
        text = re.sub(r"[\u2010-\u2015]", "-", text)  # Various dashes

        # Remove multiple blank lines
        text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)

        return text.strip()

    def _clean_item_content(self, content: str) -> str:
        """Clean extracted item content."""
        # Remove multiple spaces
        content = re.sub(r"[ ]{2,}", " ", content)
        # Remove multiple newlines
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()


# Singleton instance
item_extractor = ItemExtractor()
```

#### 2.2 Modify extraction.py to use item extraction

```python
# In extract_from_8k method, after getting clean_text:

from app.tools.item_extractor import item_extractor

# Extract items
items = item_extractor.extract_all_items(
    text=clean_text,
    filing_type="8-K",
    filing_date=filing_date
)

# Focus LLM on relevant items only
relevant_items = {}
for key, content in items.items():
    # Items that typically contain distress signals
    if key in ["item_1.01", "item_1.02", "item_1.03", "item_2.04", "item_2.05",
               "item_3.01", "item_4.01", "item_4.02", "item_5.02", "item_7.01", "item_8.01"]:
        relevant_items[key] = content

# Send structured items to LLM instead of raw text
```

---

## Phase 3: Improve Text Cleaning

**Problem:** HTML parsing leaves artifacts, broken headers, and table noise.

**Solution:** Port edgar-crawler's text cleaning pipeline.

### Files to Modify
- `app/tools/edgar.py` (add to download_filing)

### Changes

#### 3.1 Add HTML stripping with structure preservation

```python
def strip_html(self, html_content: str) -> str:
    """
    Strip HTML tags while preserving document structure.
    """
    # Add newlines after block elements
    html_content = re.sub(r"(<\s*/\s*(div|tr|p|li|)\s*>)", r"\1\n\n", html_content)
    html_content = re.sub(r"(<br\s*/?>)", r"\1\n\n", html_content)
    html_content = re.sub(r"(<\s*/\s*(th|td)\s*>)", r" \1 ", html_content)

    # Parse and extract text
    soup = BeautifulSoup(html_content, "lxml")

    # Remove script and style tags
    for tag in soup(["script", "style"]):
        tag.decompose()

    return soup.get_text(separator=" ", strip=True)
```

#### 3.2 Add table removal for numeric tables

```python
def remove_numeric_tables(self, soup: BeautifulSoup, items_list: List[str]) -> BeautifulSoup:
    """
    Remove tables that contain primarily numeric data.
    Keep tables that contain item headers.
    """
    for table in soup.find_all("table"):
        table_text = table.get_text()

        # Don't remove if contains item headers
        has_item = False
        for item in items_list:
            if re.search(rf"ITEM\s*{item}", table_text, re.IGNORECASE):
                has_item = True
                break

        if has_item:
            continue

        # Check if table has colored background (likely financial)
        rows = table.find_all(["tr", "td", "th"], attrs={"style": True})
        for row in rows:
            style = row.get("style", "")
            if "background" in style.lower():
                # Check if it's a non-white background
                if not any(c in style.lower() for c in ["#fff", "#ffffff", "white", "transparent"]):
                    table.decompose()
                    break

    return soup
```

---

## Phase 4: Rate Limiting and Retry Logic

**Problem:** SEC may rate-limit us, causing silent failures.

**Solution:** Add exponential backoff and rate limit detection.

### Files to Modify
- `app/core/rate_limiter.py`
- `app/tools/edgar.py`

### Changes

#### 4.1 Add SEC rate limit message detection

```python
SEC_RATE_LIMIT_MESSAGE = "will be managed until action is taken to declare your traffic"

def _request_html(self, url: str, retry_count: int = 5) -> str:
    """Fetch HTML with rate limit detection."""
    for attempt in range(retry_count):
        sec_edgar_limiter.acquire()

        try:
            response = requests.get(url, headers=self.headers, timeout=30)

            # Check for SEC rate limit message
            if SEC_RATE_LIMIT_MESSAGE in response.text:
                wait_time = (attempt + 1) * 2  # Exponential backoff
                logger.warning(f"SEC rate limit detected, waiting {wait_time}s")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.text

        except requests.exceptions.Timeout:
            if attempt == retry_count - 1:
                raise SECEdgarError(f"Request timeout for {url}")
            time.sleep((attempt + 1) * 0.5)
```

#### 4.2 Add requests retry session

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def requests_retry_session(
    retries: int = 5,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (500, 502, 503, 504),
) -> requests.Session:
    """Create session with automatic retry."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
```

---

## Phase 5: Historical 8-K Format Support

**Problem:** Pre-August 2004 8-Ks use different item numbering.

**Solution:** Already handled in Phase 2's item_extractor.py with date-based list selection.

---

## Phase 6: Testing and Validation

### Test Cases

1. **PLUG ticker** - Should now find signals from 2024-2025 filings
2. **Historical filing** - Test a pre-2004 8-K
3. **iXBRL filing** - Verify URL transformation works
4. **Rate limiting** - Simulate high request volume

### Validation Script

```python
# test_extraction.py
import asyncio
from app.agents.fetcher import fetcher_agent
from app.tools.item_extractor import item_extractor

async def test_plug():
    # Fetch filings
    result = await fetcher_agent.run('PLUG', months_back=24)

    print(f"Fetched {result.total_filings} filings")

    # Test item extraction on recent 8-Ks
    for filing in result.filings[:5]:
        if filing['filing_type'] == '8-K':
            items = item_extractor.extract_all_items(
                text=filing['raw_text'],
                filing_type='8-K',
                filing_date=filing['filed_at']
            )

            print(f"\n{filing['filed_at']}: Found {len(items)} items")
            for key, content in items.items():
                print(f"  {key}: {len(content)} chars")
                if 'restructur' in content.lower() or 'layoff' in content.lower():
                    print(f"    ** Contains distress keywords!")

asyncio.run(test_plug())
```

---

## Implementation Order

| Phase | Priority | Effort | Impact |
|-------|----------|--------|--------|
| 1. Fix document download | HIGH | Medium | Fixes XBRL issue |
| 2. Item extraction | HIGH | High | Clean LLM input |
| 3. Text cleaning | MEDIUM | Low | Better quality |
| 4. Rate limiting | MEDIUM | Low | Reliability |
| 5. Historical format | LOW | Low | Edge cases |
| 6. Testing | HIGH | Medium | Validation |

---

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `app/tools/edgar.py` | MODIFY | Fix download, add index parsing |
| `app/tools/item_extractor.py` | CREATE | Item-by-item extraction |
| `app/tools/extraction.py` | MODIFY | Use extracted items |
| `app/core/rate_limiter.py` | MODIFY | Add backoff logic |

---

## Rollback Plan

If issues arise:
1. Keep original `download_filing` as `download_filing_legacy`
2. Add feature flag to switch between old/new approach
3. Log all extraction failures for debugging

---

## Known Limitations

### Recovery Detection Gap

The system detects distress signals but not recovery. Companies that have successfully recovered may show elevated scores until signals age out of the 24-month window.

**Example: CVNA (Carvana)**

| Year | Status | Score |
|------|--------|-------|
| 2023 | Near bankruptcy, debt restructuring | CRITICAL (correct) |
| 2025 | Profitable, stock up 60x | CRITICAL (stale) |

The 2023 signals (RESTRUCTURING, DEBT_DEFAULT, COVENANT_VIOLATION) remain in the window even though the company recovered.

---

## Future Enhancement: Resolution Signals

Add positive signals that offset negative ones:

```python
RESOLUTION_SIGNALS = {
    "GOING_CONCERN_REMOVED": -5,      # Auditor removed GC language
    "RESTRUCTURING_COMPLETED": -4,    # Successful debt restructuring
    "DEBT_REFINANCED": -3,            # Replaced distressed debt
    "PROFITABILITY_RESTORED": -3,     # Return to positive earnings
    "CREDIT_UPGRADE": -2,             # Rating agency upgrade
}
```

**Detection approach:**
1. Compare consecutive 10-K filings for GC language removal
2. Look for 8-K announcements of successful restructuring completion
3. Track credit rating changes via Item 7.01/8.01

**Score adjustment:**
```python
# Net score = distress signals - resolution signals
if has_resolution_signal("GOING_CONCERN_REMOVED"):
    score -= RESOLUTION_SIGNALS["GOING_CONCERN_REMOVED"]
```

This would allow CVNA's score to drop from 85 → ~60 once resolution signals are detected.
