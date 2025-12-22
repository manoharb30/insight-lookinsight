"""Multi-agent orchestrator for the analysis pipeline."""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.agents.fetcher import fetcher_agent
from app.agents.extractor import extractor_agent
from app.agents.validator import validator_agent
from app.services.neo4j_service import neo4j_service
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnalysisPipeline:
    """
    Orchestrates the multi-agent analysis pipeline.

    Pipeline stages:
    1. Fetcher Agent - Get SEC filings from EDGAR
    2. Extractor Agent - Extract signals with GPT-4o
    3. Validator Agent - Validate signals, remove false positives
    4. (Future) Scorer Agent - Calculate risk score with pattern matching
    5. (Future) Reporter Agent - Generate detailed report
    """

    def __init__(self, job_id: str, jobs_store: Dict):
        self.job_id = job_id
        self.jobs = jobs_store

    def _update_job(
        self,
        stage: str,
        message: str,
        progress: int,
        signals_found: int = 0,
    ):
        """Update job status."""
        if self.job_id in self.jobs:
            self.jobs[self.job_id].update(
                {
                    "current_stage": stage,
                    "message": message,
                    "progress": progress,
                    "signals_found": signals_found,
                }
            )

    async def _update_callback(self, message: str):
        """Callback for agent progress updates."""
        current = self.jobs.get(self.job_id, {})
        self._update_job(
            stage=current.get("current_stage", "processing"),
            message=message,
            progress=current.get("progress", 0),
            signals_found=current.get("signals_found", 0),
        )

    async def run(self, ticker: str) -> Dict[str, Any]:
        """Run the full analysis pipeline."""
        try:
            # Stage 1: Fetch filings
            self._update_job("fetching", "Fetching SEC filings...", 10)

            fetch_result = await fetcher_agent.run(
                ticker=ticker,
                months_back=24,
                update_callback=self._update_callback,
            )

            if fetch_result.error:
                raise Exception(fetch_result.error)

            self._update_job(
                "fetching",
                f"Found {fetch_result.total_filings} filings",
                25,
            )

            # Stage 2: Extract signals
            self._update_job("extracting", "Extracting signals...", 30)

            extraction_result = await extractor_agent.run(
                ticker=ticker,
                company_name=fetch_result.company_name,
                filings=fetch_result.filings,
                store_embeddings=True,
                update_callback=self._update_callback,
            )

            self._update_job(
                "extracting",
                f"Extracted {extraction_result.total_signals} signals",
                60,
                signals_found=extraction_result.total_signals,
            )

            # Stage 3: Validate signals with Validator Agent
            self._update_job("validating", "Validating signals...", 70)

            validation_result = await validator_agent.run(
                ticker=ticker,
                company_name=fetch_result.company_name,
                cik=fetch_result.cik,
                signals=extraction_result.signals,
                filings=fetch_result.filings,
                store_in_neo4j=True,
                use_gpt_validation=False,  # Set True for extra validation
                update_callback=self._update_callback,
            )

            if validation_result.error:
                logger.warning(f"Validation error (continuing): {validation_result.error}")

            logger.info(
                f"Validation complete: {validation_result.total_validated}/{validation_result.total_input} "
                f"signals passed ({validation_result.validation_rate:.0%})"
            )

            self._update_job(
                "validating",
                f"Validated {validation_result.total_validated} signals "
                f"(rejected {validation_result.total_rejected})",
                80,
                signals_found=validation_result.total_validated,
            )

            # Use validated signals for rest of pipeline
            validated_signals = validation_result.validated_signals

            # Stage 4: Calculate risk score
            self._update_job("scoring", "Calculating risk score...", 85)

            risk_score = self._calculate_basic_risk_score(validated_signals)

            # Update company risk score in Neo4j
            await neo4j_service.store_company({
                "ticker": ticker,
                "cik": fetch_result.cik,
                "name": fetch_result.company_name,
                "status": "ACTIVE",
                "risk_score": risk_score,
            })

            # Stage 5: Generate result
            self._update_job("reporting", "Generating report...", 95)

            result = self._build_result(
                ticker=ticker,
                cik=fetch_result.cik,
                company_name=fetch_result.company_name,
                signals=validated_signals,
                rejected_signals=validation_result.rejected_signals,
                risk_score=risk_score,
                filings_analyzed=fetch_result.total_filings,
                validation_rate=validation_result.validation_rate,
            )

            return result

        except Exception as e:
            print(f"Pipeline error: {e}")
            raise

    def _calculate_basic_risk_score(self, signals: List[Dict[str, Any]]) -> int:
        """Calculate a basic risk score (simplified for Phase 1)."""
        weights = {
            "GOING_CONCERN": 25,
            "DEBT_DEFAULT": 20,
            "CEO_DEPARTURE": 10,
            "CFO_DEPARTURE": 10,
            "MASS_LAYOFFS": 15,
            "COVENANT_VIOLATION": 12,
            "SEC_INVESTIGATION": 8,
            "MATERIAL_WEAKNESS": 5,
            "BOARD_RESIGNATION": 5,
            "AUDITOR_CHANGE": 8,
            "DELISTING_WARNING": 15,
            "CREDIT_DOWNGRADE": 10,
            "ASSET_SALE": 8,
            "RESTRUCTURING": 10,
            "EQUITY_DILUTION": 5,
        }

        score = 0
        for signal in signals:
            signal_type = signal.get("type", "")
            severity = signal.get("severity", 5)
            base_weight = weights.get(signal_type, 5)
            score += base_weight * (severity / 7.0)

        return min(100, int(score))

    def _get_risk_level(self, score: int) -> str:
        """Convert score to risk level."""
        if score >= 70:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 30:
            return "MEDIUM"
        return "LOW"

    def _build_result(
        self,
        ticker: str,
        cik: str,
        company_name: str,
        signals: List[Dict[str, Any]],
        rejected_signals: List[Dict[str, Any]],
        risk_score: int,
        filings_analyzed: int,
        validation_rate: float,
    ) -> Dict[str, Any]:
        """Build the final result object."""
        # Group signals by type
        signal_summary = {}
        for signal in signals:
            sig_type = signal.get("type", "UNKNOWN")
            if sig_type not in signal_summary:
                signal_summary[sig_type] = 0
            signal_summary[sig_type] += 1

        # Sort signals by date
        sorted_signals = sorted(
            signals,
            key=lambda x: x.get("date", ""),
            reverse=True,
        )

        # Build timeline
        timeline = []
        for signal in sorted_signals:
            timeline.append(
                {
                    "date": signal.get("date", ""),
                    "type": signal.get("type", ""),
                    "severity": signal.get("severity", 5),
                    "confidence": signal.get("confidence", 0.8),
                    "evidence": signal.get("evidence", "")[:200] + "..."
                    if len(signal.get("evidence", "")) > 200
                    else signal.get("evidence", ""),
                    "validated": signal.get("validated", True),
                }
            )

        # Generate executive summary based on signals
        summary = self._generate_executive_summary(
            company_name, ticker, signals, risk_score
        )

        return {
            "ticker": ticker,
            "cik": cik,
            "company_name": company_name,
            "status": "ACTIVE",
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "signal_summary": signal_summary,
            "signal_count": len(signals),
            "signals": sorted_signals,
            "timeline": timeline[:20],  # Limit timeline to 20 items
            "filings_analyzed": filings_analyzed,
            "analyzed_at": datetime.utcnow().isoformat(),
            "validation": {
                "total_extracted": len(signals) + len(rejected_signals),
                "total_validated": len(signals),
                "total_rejected": len(rejected_signals),
                "validation_rate": validation_rate,
            },
            "similar_companies": [],  # Phase 3
            "bankruptcy_pattern_match": None,  # Phase 3
            "executive_summary": summary,
            "key_risks": list(signal_summary.keys())[:5],
        }

    def _generate_executive_summary(
        self,
        company_name: str,
        ticker: str,
        signals: List[Dict[str, Any]],
        risk_score: int,
    ) -> str:
        """Generate an executive summary of the analysis."""
        risk_level = self._get_risk_level(risk_score)

        if not signals:
            return (
                f"Analysis of {company_name} ({ticker}) found no significant distress "
                f"signals in recent SEC filings. Risk score: {risk_score}/100 ({risk_level})."
            )

        # Count signal types
        signal_types = {}
        for s in signals:
            t = s.get("type", "")
            signal_types[t] = signal_types.get(t, 0) + 1

        # Build summary
        top_signals = sorted(signal_types.items(), key=lambda x: x[1], reverse=True)[:3]
        signal_text = ", ".join(
            f"{count} {stype.replace('_', ' ').title()}"
            for stype, count in top_signals
        )

        severity_desc = ""
        if risk_level == "CRITICAL":
            severity_desc = "Multiple critical distress indicators detected. "
        elif risk_level == "HIGH":
            severity_desc = "Significant warning signs present. "
        elif risk_level == "MEDIUM":
            severity_desc = "Some concerns identified. "
        else:
            severity_desc = "Limited concerns. "

        return (
            f"Analysis of {company_name} ({ticker}) identified {len(signals)} validated "
            f"distress signals including {signal_text}. {severity_desc}"
            f"Risk score: {risk_score}/100 ({risk_level})."
        )
