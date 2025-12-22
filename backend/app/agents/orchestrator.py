"""Multi-agent orchestrator for the analysis pipeline."""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.agents.fetcher import fetcher_agent
from app.agents.extractor import extractor_agent
from app.services.neo4j_service import neo4j_service


class AnalysisPipeline:
    """
    Orchestrates the multi-agent analysis pipeline.

    Pipeline stages:
    1. Fetcher Agent - Get SEC filings
    2. Extractor Agent - Extract signals with GPT-4o
    3. (Future) Validator Agent - Validate signals
    4. (Future) Scorer Agent - Calculate risk score
    5. (Future) Reporter Agent - Generate report
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

            # Stage 3: Store in Neo4j (simplified validation for Phase 1)
            self._update_job("validating", "Validating signals...", 70)

            await neo4j_service.store_company(
                {
                    "ticker": ticker,
                    "cik": fetch_result.cik,
                    "name": fetch_result.company_name,
                    "status": "ACTIVE",
                    "risk_score": 0,  # Will be calculated in Phase 3
                }
            )

            for signal in extraction_result.signals:
                await neo4j_service.store_signal(
                    ticker=ticker,
                    filing_accession=signal["filing_accession"],
                    signal_data=signal,
                )

            self._update_job(
                "validating",
                f"Stored {len(extraction_result.signals)} signals",
                80,
                signals_found=len(extraction_result.signals),
            )

            # Stage 4: Calculate risk score (simplified for Phase 1)
            self._update_job("scoring", "Calculating risk score...", 85)

            risk_score = self._calculate_basic_risk_score(extraction_result.signals)

            # Stage 5: Generate result
            self._update_job("reporting", "Generating report...", 95)

            result = self._build_result(
                ticker=ticker,
                cik=fetch_result.cik,
                company_name=fetch_result.company_name,
                signals=extraction_result.signals,
                risk_score=risk_score,
                filings_analyzed=fetch_result.total_filings,
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
        risk_score: int,
        filings_analyzed: int,
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
                    "evidence": signal.get("evidence", "")[:200] + "..."
                    if len(signal.get("evidence", "")) > 200
                    else signal.get("evidence", ""),
                }
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
            "similar_companies": [],  # Phase 3
            "bankruptcy_pattern_match": None,  # Phase 3
            "executive_summary": f"Analysis of {company_name} ({ticker}) identified {len(signals)} distress signals with a risk score of {risk_score}/100.",
            "key_risks": list(signal_summary.keys())[:5],
        }
