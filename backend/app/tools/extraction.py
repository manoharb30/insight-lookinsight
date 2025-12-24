"""LLM-based signal extraction with embedding-based verbatim evidence."""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from openai import AsyncOpenAI
import json

from app.config import get_settings
from app.prompts.extraction import (
    EXTRACT_8K_PROMPT,
    EXTRACT_10K_GOING_CONCERN_PROMPT,
    SIGNAL_TYPES,
)
from app.tools.embeddings import embedding_service
from app.services.supabase_service import supabase_service
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ExtractedSignal:
    """Extracted signal from a filing."""
    signal_type: str
    severity: int
    confidence: float
    evidence: str  # Verbatim from source
    marker_phrase: str  # What LLM identified
    event_date: Optional[str]
    filing_date: str
    person: Optional[str]
    item_number: str
    filing_accession: str
    filing_type: str
    evidence_verified: bool  # True if evidence found in source


class SignalExtractor:
    """
    Extract bankruptcy signals using LLM + embedding-based evidence verification.

    Flow:
    1. LLM reads filing, identifies signals with marker phrases
    2. Embed marker phrase
    3. Semantic search to find matching text in filing
    4. Extract verbatim evidence from source
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_concurrent: int = 5,
        max_filing_chars: int = 50000,
        evidence_context_chars: int = 300,  # Chars before/after marker
    ):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model
        self.max_concurrent = max_concurrent
        self.max_filing_chars = max_filing_chars
        self.evidence_context_chars = evidence_context_chars

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Create a new semaphore for the current event loop."""
        return asyncio.Semaphore(self.max_concurrent)

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean up text."""
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()

    def _chunk_filing(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Split filing into overlapping chunks for embedding.

        Returns list of {content, char_start, char_end, position}
        """
        chunks = []
        start = 0
        position = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period > start + chunk_size // 2:
                    end = last_period + 1

            chunks.append({
                'content': text[start:end],
                'char_start': start,
                'char_end': end,
                'position': position,
            })

            position += 1
            start = end - overlap if end < len(text) else end

        return chunks

    async def _embed_and_store_filing(
        self,
        filing_accession: str,
        clean_text: str,
        ticker: str = "",
        cik: str = "",
        filing_type: str = "8-K",
    ) -> bool:
        """
        Chunk filing, generate embeddings, store in Supabase.

        Returns True if successful.
        """
        try:
            # Check if already embedded
            existing = await supabase_service.chunks_exist_for_filing(filing_accession)
            if existing:
                logger.debug(f"Filing {filing_accession} already embedded")
                return True

            # Chunk the filing
            chunks = self._chunk_filing(clean_text)

            if not chunks:
                return False

            # Generate embeddings in batches
            batch_size = 20
            all_chunks_with_embeddings = []

            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                texts = [c['content'] for c in batch]

                embeddings = await embedding_service.embed_batch_async(texts)

                for chunk, embedding in zip(batch, embeddings):
                    if embedding:
                        chunk['embedding'] = embedding
                        all_chunks_with_embeddings.append(chunk)

            # Store in Supabase
            if all_chunks_with_embeddings:
                await supabase_service.store_filing_chunks(
                    filing_accession=filing_accession,
                    chunks=all_chunks_with_embeddings,
                    ticker=ticker,
                    cik=cik,
                    filing_type=filing_type,
                )

            return True

        except Exception as e:
            logger.error(f"Error embedding filing {filing_accession}: {e}")
            return False

    async def _find_verbatim_evidence(
        self,
        marker_phrase: str,
        filing_accession: str,
        source_text: str,
    ) -> Tuple[str, bool]:
        """
        Find verbatim evidence in source using embedding search.

        Args:
            marker_phrase: The phrase LLM identified
            filing_accession: Filing to search in
            source_text: Original filing text (fallback)

        Returns:
            Tuple of (evidence_text, was_verified)
        """
        try:
            # First try exact string match (fastest)
            marker_lower = marker_phrase.lower()
            source_lower = source_text.lower()

            pos = source_lower.find(marker_lower)
            if pos != -1:
                # Found exact match - extract context
                start = max(0, pos - self.evidence_context_chars)
                end = min(len(source_text), pos + len(marker_phrase) + self.evidence_context_chars)

                # Try to start/end at sentence boundaries
                if start > 0:
                    period_pos = source_text.rfind('.', max(0, start - 50), start)
                    if period_pos != -1:
                        start = period_pos + 2

                if end < len(source_text):
                    period_pos = source_text.find('.', end, min(len(source_text), end + 50))
                    if period_pos != -1:
                        end = period_pos + 1

                evidence = source_text[start:end].strip()
                logger.info(f"Evidence verified via exact match")
                return evidence, True

            # Fallback to semantic search
            logger.debug(f"Exact match failed, trying semantic search")

            marker_embedding = await embedding_service.embed_text_async(marker_phrase)
            if not marker_embedding:
                return marker_phrase, False

            results = await supabase_service.semantic_search_in_filing(
                query_embedding=marker_embedding,
                filing_accession=filing_accession,
                top_k=1,
                similarity_threshold=0.6,
            )

            if results:
                best_match = results[0]
                evidence = best_match.get('content', marker_phrase)
                similarity = best_match.get('similarity', 0)
                logger.info(f"Evidence verified via semantic search (similarity: {similarity:.2f})")
                return evidence, True

            # Last fallback - return marker phrase as evidence (unverified)
            logger.warning(f"Could not verify evidence for marker: {marker_phrase[:50]}...")
            return marker_phrase, False

        except Exception as e:
            logger.error(f"Error finding verbatim evidence: {e}")
            return marker_phrase, False

    async def extract_from_8k(
        self,
        filing_data: Dict[str, Any],
        company_name: str,
        semaphore: asyncio.Semaphore,
        ticker: str = "",
        cik: str = "",
    ) -> List[ExtractedSignal]:
        """
        Extract signals from a full 8-K filing using LLM.
        Then verify evidence using embeddings.
        """
        async with semaphore:
            try:
                raw_text = filing_data.get("raw_text", "")
                if not raw_text:
                    logger.warning(f"Empty 8-K filing: {filing_data.get('accession_number')}")
                    return []

                clean_text = self._clean_html(raw_text)
                if len(clean_text) > self.max_filing_chars:
                    logger.info(f"Truncating 8-K from {len(clean_text)} to {self.max_filing_chars} chars")
                    clean_text = clean_text[:self.max_filing_chars]

                filing_date = filing_data.get("filed_at", "")
                accession = filing_data.get("accession_number", "")

                # Step 1: Embed and store filing chunks (for later search)
                await self._embed_and_store_filing(
                    accession, clean_text, ticker, cik, "8-K"
                )

                # Step 2: LLM extracts signals with marker phrases
                prompt = EXTRACT_8K_PROMPT.format(
                    company_name=company_name,
                    filing_date=filing_date,
                    accession_number=accession,
                    filing_text=clean_text,
                )

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert SEC filing analyst. Extract signals with VERBATIM marker phrases. Return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=2000,
                )

                content = response.choices[0].message.content
                result = json.loads(content)

                # Step 3: For each signal, find verbatim evidence
                signals = []
                for sig in result.get("signals", []):
                    if sig.get("type") not in SIGNAL_TYPES:
                        logger.warning(f"Unknown signal type: {sig.get('type')}")
                        continue

                    marker_phrase = sig.get("marker_phrase", "")
                    if not marker_phrase:
                        logger.warning(f"No marker phrase for signal {sig.get('type')}")
                        continue

                    # Find verbatim evidence
                    evidence, verified = await self._find_verbatim_evidence(
                        marker_phrase=marker_phrase,
                        filing_accession=accession,
                        source_text=clean_text,
                    )

                    signals.append(ExtractedSignal(
                        signal_type=sig["type"],
                        severity=min(10, max(1, sig.get("severity", 5))),
                        confidence=min(1.0, max(0.0, sig.get("confidence", 0.8))),
                        evidence=evidence[:500],  # Cap at 500 chars
                        marker_phrase=marker_phrase,
                        event_date=sig.get("event_date") or filing_date,
                        filing_date=filing_date,
                        person=sig.get("person"),
                        item_number=sig.get("item_number", ""),
                        filing_accession=accession,
                        filing_type="8-K",
                        evidence_verified=verified,
                    ))

                logger.info(f"Extracted {len(signals)} signals from 8-K {accession}")
                return signals

            except Exception as e:
                logger.error(f"Error extracting from 8-K: {e}")
                return []

    async def extract_going_concern_from_10k(
        self,
        filing_data: Dict[str, Any],
        company_name: str,
        semaphore: asyncio.Semaphore,
        ticker: str = "",
        cik: str = "",
    ) -> List[ExtractedSignal]:
        """
        Extract GOING_CONCERN signal from 10-K using keyword search + LLM.
        Then verify evidence using embeddings.
        """
        async with semaphore:
            try:
                raw_text = filing_data.get("raw_text", "")
                if not raw_text:
                    logger.warning(f"Empty 10-K filing: {filing_data.get('accession_number')}")
                    return []

                clean_text = self._clean_html(raw_text)
                filing_date = filing_data.get("filed_at", "")
                accession = filing_data.get("accession_number", "")

                # Search on clean text
                search_text = clean_text.lower()

                going_concern_keywords = [
                    "going concern",
                    "substantial doubt",
                    "ability to continue as a going concern",
                    "continue as a going concern",
                ]

                keyword_found = False
                keyword_position = -1

                for keyword in going_concern_keywords:
                    pos = search_text.find(keyword)
                    if pos != -1:
                        keyword_found = True
                        keyword_position = pos
                        logger.info(f"Found '{keyword}' in 10-K {accession} at position {pos}")
                        break

                if not keyword_found:
                    logger.info(f"No going concern keywords in 10-K {accession}")
                    return []

                # Extract context around keyword
                start = max(0, keyword_position - 3000)
                end = min(len(clean_text), keyword_position + 3000)
                excerpt = clean_text[start:end]

                if len(excerpt.strip()) < 100:
                    return []

                # Embed the filing for later verification
                await self._embed_and_store_filing(
                    accession, clean_text, ticker, cik, "10-K"
                )

                prompt = EXTRACT_10K_GOING_CONCERN_PROMPT.format(
                    company_name=company_name,
                    filing_date=filing_date,
                    accession_number=accession,
                    excerpt_text=excerpt,
                )

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert SEC filing analyst. Return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=500,
                )

                content = response.choices[0].message.content
                result = json.loads(content)

                if not result.get("has_going_concern"):
                    logger.info(f"10-K {accession}: Going concern keyword found but not a warning")
                    return []

                sig = result.get("signal")
                if not sig:
                    return []

                marker_phrase = sig.get("marker_phrase", "")

                # Find verbatim evidence
                if marker_phrase:
                    evidence, verified = await self._find_verbatim_evidence(
                        marker_phrase=marker_phrase,
                        filing_accession=accession,
                        source_text=clean_text,
                    )
                else:
                    evidence = sig.get("evidence", "")
                    verified = False

                signal = ExtractedSignal(
                    signal_type="GOING_CONCERN",
                    severity=min(10, max(1, sig.get("severity", 9))),
                    confidence=min(1.0, max(0.0, sig.get("confidence", 0.9))),
                    evidence=evidence[:500],
                    marker_phrase=marker_phrase,
                    event_date=filing_date,
                    filing_date=filing_date,
                    person=None,
                    item_number="Auditor Report",
                    filing_accession=accession,
                    filing_type="10-K",
                    evidence_verified=verified,
                )

                logger.info(f"Extracted GOING_CONCERN from 10-K {accession}")
                return [signal]

            except Exception as e:
                logger.error(f"Error extracting going concern from 10-K: {e}")
                return []

    async def extract_from_filings(
        self,
        filings: List[Dict[str, Any]],
        company_name: str,
        ticker: str = "",
        cik: str = "",
        update_callback=None,
    ) -> List[ExtractedSignal]:
        """
        Extract signals from all filings in parallel.
        """
        # Create semaphore for this event loop
        semaphore = self._get_semaphore()

        tasks = []

        eight_k_count = 0
        ten_k_count = 0

        for filing in filings:
            filing_type = filing.get("filing_type", "")

            if filing_type == "8-K":
                eight_k_count += 1
                tasks.append(self.extract_from_8k(
                    filing, company_name, semaphore, ticker, cik
                ))

            elif filing_type == "10-K":
                ten_k_count += 1
                tasks.append(self.extract_going_concern_from_10k(
                    filing, company_name, semaphore, ticker, cik
                ))

            elif filing_type == "10-Q":
                logger.warning("10-Q filing in list - should be excluded by fetcher")
                continue

        if update_callback:
            await update_callback(
                f"Extracting signals from {eight_k_count} 8-K and {ten_k_count} 10-K filings..."
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_signals = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Extraction failed: {result}")
                continue
            all_signals.extend(result)

        if update_callback:
            verified_count = sum(1 for s in all_signals if s.evidence_verified)
            await update_callback(
                f"Extracted {len(all_signals)} signals ({verified_count} with verified evidence)"
            )

        return all_signals


# Singleton instance
signal_extractor = SignalExtractor(max_concurrent=5)
