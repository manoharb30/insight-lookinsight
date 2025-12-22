"""Agent 2: Signal Extractor - GPT-4o signal extraction with chunking."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid

from app.tools.chunker import chunker, Chunk
from app.tools.embeddings import embeddings_client
from app.tools.extraction import signal_extractor, ExtractedSignal
from app.services.supabase_service import supabase_service


@dataclass
class ExtractionResult:
    ticker: str
    signals: List[Dict[str, Any]]
    total_chunks: int
    total_signals: int
    chunks_processed: int
    error: Optional[str] = None


class SignalExtractorAgent:
    """
    Agent 2: Financial Distress Signal Analyst

    Role: Extract bankruptcy warning signals from SEC filings
    Goal: Extract signals with exact evidence using GPT-4o
    """

    def __init__(self):
        self.role = "Financial Distress Signal Analyst"
        self.goal = "Extract bankruptcy warning signals from SEC filings with exact evidence"
        self.backstory = "Senior financial analyst specializing in corporate distress indicators"

    async def run(
        self,
        ticker: str,
        cik: str,
        company_name: str,
        filings: List[Dict[str, Any]],
        store_embeddings: bool = True,
        update_callback=None,
    ) -> ExtractionResult:
        """
        Extract signals from filings.

        Args:
            ticker: Stock ticker
            cik: Company CIK
            company_name: Company name
            filings: List of filing data from fetcher
            store_embeddings: Whether to store chunk embeddings in Supabase
            update_callback: Optional callback for progress updates
        """
        all_signals = []
        total_chunks = 0
        chunks_processed = 0

        for filing_idx, filing in enumerate(filings):
            if update_callback:
                await update_callback(
                    f"Processing filing {filing_idx + 1}/{len(filings)}..."
                )

            # Skip filings with errors
            if "error" in filing:
                continue

            # Chunk the filing
            chunks = chunker.chunk_for_extraction(filing)
            total_chunks += len(chunks)

            # Prepare chunks for embedding (batch)
            chunk_texts = [c.content for c in chunks]

            # Generate embeddings
            if store_embeddings and chunk_texts:
                try:
                    embeddings = embeddings_client.embed_texts(chunk_texts)

                    # Store in Supabase
                    chunk_data = [
                        {
                            "content": chunks[i].content,
                            "item_number": chunks[i].item_number,
                            "embedding": embeddings[i],
                        }
                        for i in range(len(chunks))
                    ]

                    await supabase_service.store_filing_chunks_batch(
                        ticker=ticker,
                        cik=cik,
                        accession_number=filing["accession_number"],
                        filing_type=filing["filing_type"],
                        chunks=chunk_data,
                    )
                except Exception as e:
                    print(f"Error storing embeddings: {e}")

            # Extract signals from each chunk
            for chunk in chunks:
                signals = signal_extractor.extract_signals(
                    text=chunk.content,
                    item_number=chunk.item_number,
                    filing_date=filing.get("filed_at", ""),
                    company_name=company_name,
                )

                for signal in signals:
                    signal_dict = {
                        "signal_id": str(uuid.uuid4()),
                        "type": signal.signal_type,
                        "severity": signal.severity,
                        "confidence": signal.confidence,
                        "evidence": signal.evidence,
                        "date": signal.date,
                        "person": signal.person,
                        "item_number": signal.item_number,
                        "filing_accession": filing["accession_number"],
                        "filing_type": filing["filing_type"],
                    }
                    all_signals.append(signal_dict)

                chunks_processed += 1

            if update_callback:
                await update_callback(
                    f"Extracted {len(all_signals)} signals so far..."
                )

        if update_callback:
            await update_callback(
                f"Extraction complete: {len(all_signals)} signals from {chunks_processed} chunks"
            )

        return ExtractionResult(
            ticker=ticker,
            signals=all_signals,
            total_chunks=total_chunks,
            total_signals=len(all_signals),
            chunks_processed=chunks_processed,
        )


# Singleton instance
extractor_agent = SignalExtractorAgent()
