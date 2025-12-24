"""Agent 2: Signal Extractor - LLM-based full filing extraction with verified evidence."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid

from app.tools.extraction import signal_extractor, ExtractedSignal
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    ticker: str
    signals: List[Dict[str, Any]]
    total_filings: int
    eight_k_count: int
    ten_k_count: int
    total_signals: int
    verified_signals: int  # Count of signals with verified evidence
    error: Optional[str] = None


class SignalExtractorAgent:
    """
    Agent 2: Financial Distress Signal Analyst

    Uses LLM on full filing text + embeddings for verbatim evidence verification.
    - 8-K: Full text extraction (all signal types)
    - 10-K: Going concern only (keyword search + LLM)
    """

    def __init__(self):
        self.role = "Financial Distress Signal Analyst"
        self.goal = "Extract bankruptcy warning signals with verified evidence"

    async def run(
        self,
        ticker: str,
        cik: str,
        company_name: str,
        filings: List[Dict[str, Any]],
        update_callback=None,
    ) -> ExtractionResult:
        """Extract signals from filings using LLM + embedding verification."""

        # Count filing types
        eight_k_filings = [f for f in filings if f.get("filing_type") == "8-K"]
        ten_k_filings = [f for f in filings if f.get("filing_type") == "10-K"]

        if update_callback:
            await update_callback(
                f"Processing {len(eight_k_filings)} 8-K and {len(ten_k_filings)} 10-K filings..."
            )

        # Extract signals in parallel with ticker/cik for embedding storage
        extracted_signals = await signal_extractor.extract_from_filings(
            filings=filings,
            company_name=company_name,
            ticker=ticker,
            cik=cik,
            update_callback=update_callback,
        )

        # Convert to dict format for pipeline
        signals = []
        verified_count = 0

        for sig in extracted_signals:
            if sig.evidence_verified:
                verified_count += 1

            signals.append({
                "signal_id": str(uuid.uuid4()),
                "type": sig.signal_type,
                "severity": sig.severity,
                "confidence": sig.confidence,
                "evidence": sig.evidence,
                "marker_phrase": sig.marker_phrase,
                "evidence_verified": sig.evidence_verified,
                "date": sig.event_date or sig.filing_date,
                "person": sig.person,
                "item_number": sig.item_number,
                "filing_accession": sig.filing_accession,
                "filing_type": sig.filing_type,
            })

        if update_callback:
            await update_callback(
                f"Extraction complete: {len(signals)} signals "
                f"({verified_count} with verified evidence)"
            )

        return ExtractionResult(
            ticker=ticker,
            signals=signals,
            total_filings=len(filings),
            eight_k_count=len(eight_k_filings),
            ten_k_count=len(ten_k_filings),
            total_signals=len(signals),
            verified_signals=verified_count,
        )


# Singleton instance
extractor_agent = SignalExtractorAgent()
