"""Multi-agent orchestrator for the analysis pipeline.

Facts-only approach: NO risk scores, NO predictions.
"""

from typing import Dict, Any
from datetime import datetime

from app.agents.fetcher import fetcher_agent
from app.agents.extractor import extractor_agent
from app.agents.validator import validator_agent
from app.agents.reporter import reporter_agent
from app.services.neo4j_sync_service import neo4j_sync_service
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnalysisPipeline:
    """
    Orchestrates the multi-agent analysis pipeline.

    Facts-only pipeline (NO SCORING):
    1. Fetch 8-K + 10-K only
    2. LLM extraction on full filings
    3. Deduplicate (type + date)
    4. Validate
    5. Sync to Neo4j (facts only)
    6. Generate report (facts only)
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
        if self.job_id in self.jobs:
            self.jobs[self.job_id].update({
                "current_stage": stage,
                "message": message,
                "progress": progress,
                "signals_found": signals_found,
            })

    async def _update_callback(self, message: str):
        current = self.jobs.get(self.job_id, {})
        self._update_job(
            stage=current.get("current_stage", "processing"),
            message=message,
            progress=current.get("progress", 0),
            signals_found=current.get("signals_found", 0),
        )

    async def run(self, ticker: str) -> Dict[str, Any]:
        """Run the full analysis pipeline - facts only."""
        try:
            # Stage 1: Fetch 8-K + 10-K filings (0-25%)
            self._update_job("fetching", "Fetching SEC filings (8-K + 10-K only)...", 5)

            fetch_result = await fetcher_agent.run(
                ticker=ticker,
                months_back=24,
                update_callback=self._update_callback,
            )

            if fetch_result.error:
                raise Exception(fetch_result.error)

            self._update_job(
                "fetching",
                f"Fetched {fetch_result.total_filings} filings "
                f"({fetch_result.filings_by_type.get('8-K', 0)} 8-K, "
                f"{fetch_result.filings_by_type.get('10-K', 0)} 10-K)",
                25,
            )

            # Stage 2: Extract signals using LLM (25-60%)
            self._update_job("extracting", "Extracting signals with LLM...", 30)

            extraction_result = await extractor_agent.run(
                ticker=ticker,
                cik=fetch_result.cik,
                company_name=fetch_result.company_name,
                filings=fetch_result.filings,
                update_callback=self._update_callback,
            )

            self._update_job(
                "extracting",
                f"Extracted {extraction_result.total_signals} raw signals",
                60,
                signals_found=extraction_result.total_signals,
            )

            # Stage 3: Validate and deduplicate (60-80%)
            self._update_job("validating", "Validating and deduplicating...", 65)

            validation_result = await validator_agent.run(
                ticker=ticker,
                company_name=fetch_result.company_name,
                cik=fetch_result.cik,
                signals=extraction_result.signals,
                filings=fetch_result.filings,
                store_in_neo4j=True,
                use_gpt_validation=False,
                update_callback=self._update_callback,
            )

            if validation_result.error:
                logger.warning(f"Validation error: {validation_result.error}")

            self._update_job(
                "validating",
                f"Validated {validation_result.total_validated} signals",
                80,
                signals_found=validation_result.total_validated,
            )

            validated_signals = validation_result.validated_signals

            # Stage 4: Sync to Neo4j (80-90%) - FACTS ONLY
            self._update_job("syncing", "Syncing to timeline graph...", 85)

            try:
                sync_result = await neo4j_sync_service.sync_from_analysis(
                    ticker=ticker,
                    company_data={
                        "cik": fetch_result.cik,
                        "name": fetch_result.company_name,
                        "status": "ACTIVE",
                    },
                    signals=validated_signals,
                )
                self._update_job(
                    "syncing",
                    f"Synced {sync_result.get('signals_created', 0)} signals to Neo4j",
                    90,
                    signals_found=validation_result.total_validated,
                )
            except Exception as e:
                logger.warning(f"Neo4j sync error (non-fatal): {e}")
                sync_result = {"error": str(e)}

            # Stage 5: Generate report (90-100%) - FACTS ONLY
            self._update_job("reporting", "Generating report...", 95)

            report = await reporter_agent.run(
                ticker=ticker,
                cik=fetch_result.cik,
                company_name=fetch_result.company_name,
                signals=validated_signals,
                rejected_signals=validation_result.rejected_signals,
                filings_analyzed=fetch_result.total_filings,
                update_callback=self._update_callback,
            )

            result = reporter_agent.to_dict(report)

            # Add summary stats
            result["extraction_stats"] = {
                "filings_fetched": fetch_result.total_filings,
                "eight_k_count": fetch_result.filings_by_type.get("8-K", 0),
                "ten_k_count": fetch_result.filings_by_type.get("10-K", 0),
                "raw_signals": extraction_result.total_signals,
                "validated_signals": validation_result.total_validated,
                "signals_by_type": validation_result.signals_by_type,
            }

            # Add sync info
            if "error" not in sync_result:
                result["neo4j_sync"] = {
                    "signals_synced": sync_result.get("signals_created", 0),
                    "going_concern_status": sync_result.get("going_concern_status"),
                }

            return result

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            raise
