"""Agent 3: Signal Validator - Validates and deduplicates signals."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.tools.validation import signal_validator
from app.tools.deduplication import deduplicate_signals
from app.tools.evidence_filter import filter_signals_by_evidence_quality
from app.services.neo4j_service import neo4j_service
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationOutput:
    ticker: str
    validated_signals: List[Dict[str, Any]]
    rejected_signals: List[Dict[str, Any]]
    total_input: int
    total_validated: int
    total_rejected: int
    validation_rate: float
    signals_by_type: Dict[str, int]
    error: Optional[str] = None


class SignalValidatorAgent:
    """
    Agent 3: Signal Quality Assurance Specialist

    Simplified pipeline:
    1. Evidence quality filter (remove junk)
    2. Deduplication (type + date based)
    3. Rule validation
    """

    def __init__(self):
        self.role = "Signal Quality Assurance Specialist"
        self.goal = "Validate signals and eliminate duplicates"

    async def run(
        self,
        ticker: str,
        company_name: str,
        cik: str,
        signals: List[Dict[str, Any]],
        filings: Optional[List[Dict[str, Any]]] = None,
        store_in_neo4j: bool = True,
        use_gpt_validation: bool = False,
        update_callback=None,
    ) -> ValidationOutput:
        """Validate and deduplicate signals."""

        if update_callback:
            await update_callback(f"Validating {len(signals)} raw signals...")

        original_count = len(signals)
        all_rejected = []

        # STEP 1: Evidence quality filter
        if update_callback:
            await update_callback("Filtering by evidence quality...")

        signals, rejected_quality = filter_signals_by_evidence_quality(signals)
        all_rejected.extend(rejected_quality)

        logger.info(f"After quality filter: {len(signals)} signals (rejected {len(rejected_quality)})")

        # STEP 2: Deduplication (type + date based)
        if update_callback:
            await update_callback("Removing duplicates...")

        dedup_result = deduplicate_signals(signals)
        signals = dedup_result.unique_signals

        logger.info(f"After deduplication: {len(signals)} signals (removed {dedup_result.duplicates_removed})")

        # STEP 3: LLM validation
        if update_callback:
            await update_callback("Validating signals with LLM...")

        validated_signals, rejected_rules = await signal_validator.validate_signals_async(
            signals=signals,
            use_llm=True,  # Always use LLM validation
        )
        all_rejected.extend(rejected_rules)

        logger.info(f"After LLM validation: {len(validated_signals)} signals (rejected {len(rejected_rules)})")

        # Store in Neo4j
        if store_in_neo4j and validated_signals:
            await self._store_signals_in_neo4j(
                ticker=ticker,
                company_name=company_name,
                cik=cik,
                signals=validated_signals,
                update_callback=update_callback,
            )

        # Calculate final stats
        validation_rate = len(validated_signals) / original_count if original_count > 0 else 0.0

        # Count by type
        signals_by_type = {}
        for sig in validated_signals:
            sig_type = sig.get("type", "UNKNOWN")
            signals_by_type[sig_type] = signals_by_type.get(sig_type, 0) + 1

        if update_callback:
            await update_callback(
                f"Validation complete: {len(validated_signals)} signals "
                f"({validation_rate:.0%} pass rate)"
            )

        return ValidationOutput(
            ticker=ticker,
            validated_signals=validated_signals,
            rejected_signals=all_rejected,
            total_input=original_count,
            total_validated=len(validated_signals),
            total_rejected=len(all_rejected),
            validation_rate=validation_rate,
            signals_by_type=signals_by_type,
        )

    async def _store_signals_in_neo4j(
        self,
        ticker: str,
        company_name: str,
        cik: str,
        signals: List[Dict[str, Any]],
        update_callback=None,
    ) -> None:
        """Store validated signals in Neo4j."""
        try:
            if update_callback:
                await update_callback("Storing signals in Neo4j...")

            await neo4j_service.store_company({
                "ticker": ticker,
                "cik": cik,
                "name": company_name,
                "status": "ACTIVE",
                "risk_score": 0,
            })

            filings_stored = set()
            for signal in signals:
                filing_accession = signal.get("filing_accession", "")
                filing_type = signal.get("filing_type", "")
                date = signal.get("date", "")

                if filing_accession and filing_accession not in filings_stored:
                    await neo4j_service.store_filing(
                        ticker=ticker,
                        filing_data={
                            "accession_number": filing_accession,
                            "filing_type": filing_type,
                            "filed_at": date,
                            "url": "",
                        },
                    )
                    filings_stored.add(filing_accession)

                if filing_accession:
                    await neo4j_service.store_signal(
                        ticker=ticker,
                        filing_accession=filing_accession,
                        signal_data={
                            "signal_id": signal.get("signal_id"),
                            "type": signal.get("type"),
                            "severity": signal.get("severity"),
                            "confidence": signal.get("confidence"),
                            "evidence": signal.get("evidence", ""),
                            "date": date,
                            "item_number": signal.get("item_number", ""),
                            "person": signal.get("person"),
                        },
                    )

            logger.info(f"Stored {len(signals)} signals in Neo4j")

        except Exception as e:
            logger.error(f"Error storing signals in Neo4j: {e}")


# Singleton instance
validator_agent = SignalValidatorAgent()
