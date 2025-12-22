"""Multi-agent orchestrator for the analysis pipeline."""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.agents.fetcher import fetcher_agent
from app.agents.extractor import extractor_agent
from app.agents.validator import validator_agent
from app.agents.scorer import scorer_agent
from app.agents.reporter import reporter_agent
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
    4. Scorer Agent - Calculate risk score with Neo4j pattern matching
    5. Reporter Agent - Generate detailed analysis report
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
                cik=fetch_result.cik,
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

            # Stage 4: Calculate risk score with Scorer Agent
            self._update_job("scoring", "Calculating risk score...", 85)

            risk_assessment = await scorer_agent.run(
                ticker=ticker,
                signals=validated_signals,
                update_callback=self._update_callback,
            )

            self._update_job(
                "scoring",
                f"Risk score: {risk_assessment.risk_score}/100 ({risk_assessment.risk_level})",
                90,
                signals_found=validation_result.total_validated,
            )

            # Stage 5: Generate report with Reporter Agent
            self._update_job("reporting", "Generating report...", 95)

            report = await reporter_agent.run(
                ticker=ticker,
                cik=fetch_result.cik,
                company_name=fetch_result.company_name,
                signals=validated_signals,
                rejected_signals=validation_result.rejected_signals,
                risk_assessment=risk_assessment,
                filings_analyzed=fetch_result.total_filings,
                update_callback=self._update_callback,
            )

            # Convert report to dict for API response
            result = reporter_agent.to_dict(report)

            return result

        except Exception as e:
            print(f"Pipeline error: {e}")
            raise
