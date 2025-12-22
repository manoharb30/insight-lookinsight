"""Agent 3: Signal Validator - Validates extracted signals and removes false positives."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.tools.validation import signal_validator, ValidationResult
from app.services.neo4j_service import neo4j_service
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationOutput:
    """Output from the validator agent."""
    ticker: str
    validated_signals: List[Dict[str, Any]]
    rejected_signals: List[Dict[str, Any]]
    total_input: int
    total_validated: int
    total_rejected: int
    validation_rate: float
    error: Optional[str] = None


class SignalValidatorAgent:
    """
    Agent 3: Signal Quality Assurance Specialist

    Role: Validate extracted signals and eliminate false positives
    Goal: Ensure only high-quality, verified signals are stored
    Backstory: Forensic accountant with expertise in separating real signals from noise
    """

    def __init__(self):
        self.role = "Signal Quality Assurance Specialist"
        self.goal = "Validate signals and eliminate false positives and hallucinations"
        self.backstory = "Forensic accountant with expertise in separating real signals from noise"

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
        """
        Validate extracted signals.

        Args:
            ticker: Stock ticker
            company_name: Company name
            cik: Company CIK
            signals: List of raw signals from extractor
            filings: Optional list of filing data (for evidence verification)
            store_in_neo4j: Whether to store validated signals in Neo4j
            use_gpt_validation: Whether to use GPT for edge case validation
            update_callback: Optional callback for progress updates

        Returns:
            ValidationOutput with validated and rejected signals
        """
        if update_callback:
            await update_callback(f"Validating {len(signals)} signals...")

        # Build source text mapping for evidence verification
        source_texts = {}
        if filings:
            for filing in filings:
                if "raw_text" in filing and "accession_number" in filing:
                    source_texts[filing["accession_number"]] = filing["raw_text"]

        # Run validation
        validated_signals, rejected_signals = signal_validator.validate_signals(
            signals=signals,
            source_texts=source_texts if source_texts else None,
            use_gpt=use_gpt_validation,
        )

        if update_callback:
            await update_callback(
                f"Validated {len(validated_signals)} signals, rejected {len(rejected_signals)}"
            )

        # Store validated signals in Neo4j
        if store_in_neo4j and validated_signals:
            await self._store_signals_in_neo4j(
                ticker=ticker,
                company_name=company_name,
                cik=cik,
                signals=validated_signals,
                update_callback=update_callback,
            )

        # Calculate validation rate
        total = len(signals)
        validation_rate = len(validated_signals) / total if total > 0 else 0.0

        # Log rejected signals for debugging
        if rejected_signals:
            logger.info(f"Rejected {len(rejected_signals)} signals for {ticker}:")
            for sig in rejected_signals[:5]:  # Log first 5
                logger.debug(
                    f"  - {sig.get('type')}: {sig.get('rejection_reason')}"
                )

        if update_callback:
            await update_callback(
                f"Validation complete: {len(validated_signals)}/{total} signals passed ({validation_rate:.0%})"
            )

        return ValidationOutput(
            ticker=ticker,
            validated_signals=validated_signals,
            rejected_signals=rejected_signals,
            total_input=total,
            total_validated=len(validated_signals),
            total_rejected=len(rejected_signals),
            validation_rate=validation_rate,
        )

    async def _store_signals_in_neo4j(
        self,
        ticker: str,
        company_name: str,
        cik: str,
        signals: List[Dict[str, Any]],
        update_callback=None,
    ) -> None:
        """Store validated signals in Neo4j graph database."""
        try:
            if update_callback:
                await update_callback("Storing signals in Neo4j...")

            # Store company node first
            await neo4j_service.store_company({
                "ticker": ticker,
                "cik": cik,
                "name": company_name,
                "status": "ACTIVE",
                "risk_score": 0,  # Will be updated by scorer agent
            })

            # Store each filing and its signals
            filings_stored = set()
            for signal in signals:
                filing_accession = signal.get("filing_accession", "")
                filing_type = signal.get("filing_type", "")
                date = signal.get("date", "")

                # Store filing if not already stored
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

                # Store the signal
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

            logger.info(
                f"Stored {len(signals)} signals in Neo4j for {ticker} "
                f"({len(filings_stored)} filings)"
            )

            if update_callback:
                await update_callback(f"Stored {len(signals)} signals in Neo4j")

        except Exception as e:
            logger.error(f"Error storing signals in Neo4j: {e}")
            # Don't raise - validation still succeeded even if storage failed

    async def validate_single(
        self,
        signal: Dict[str, Any],
        source_text: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a single signal.

        Args:
            signal: Signal dict
            source_text: Optional source text for evidence verification

        Returns:
            ValidationResult
        """
        return signal_validator.validate_signal(signal, source_text)


# Singleton instance
validator_agent = SignalValidatorAgent()
