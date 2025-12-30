"""Agent 5: Report Generator - Facts-only analysis report.

NO risk scores, NO predictions. Just facts from SEC filings.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TimelineEvent:
    """Event in the signal timeline."""
    date: str
    type: str
    evidence: str
    filing_type: str
    filing_accession: str
    item_number: str


@dataclass
class AnalysisReport:
    """Complete analysis report - FACTS ONLY, NO SCORES."""
    # Company info
    ticker: str
    cik: str
    company_name: str
    status: str

    # Signal data (facts only)
    signal_count: int
    signal_summary: Dict[str, int]
    signals: List[Dict[str, Any]]
    timeline: List[TimelineEvent]

    # Going concern tracking
    going_concern_status: str  # "ACTIVE" | "REMOVED" | "NEVER"
    going_concern_first_seen: Optional[str]
    going_concern_last_seen: Optional[str]

    # Timeline context
    first_signal_date: Optional[str]
    last_signal_date: Optional[str]
    days_since_last_signal: Optional[int]

    # Validation stats
    validation: Dict[str, Any]

    # Metadata
    filings_analyzed: int
    analyzed_at: str
    expires_at: str


class ReportGeneratorAgent:
    """
    Agent 5: Financial Report Writer - Facts Only

    Role: Generate factual reports from SEC filings
    Goal: Present signals with evidence - no judgments or predictions
    """

    def __init__(self):
        self.role = "Financial Report Writer"
        self.goal = "Present factual findings from SEC filings"

    async def run(
        self,
        ticker: str,
        cik: str,
        company_name: str,
        signals: List[Dict[str, Any]],
        rejected_signals: List[Dict[str, Any]],
        filings_analyzed: int,
        update_callback=None,
        risk_assessment=None,  # DEPRECATED - kept for backward compatibility
    ) -> AnalysisReport:
        """
        Generate factual analysis report.

        Args:
            ticker: Stock ticker
            cik: Company CIK
            company_name: Company name
            signals: Validated signals
            rejected_signals: Signals that failed validation
            filings_analyzed: Number of filings analyzed
            update_callback: Optional callback for progress updates
            risk_assessment: DEPRECATED - kept for backward compatibility

        Returns:
            AnalysisReport with facts only
        """
        if update_callback:
            await update_callback("Generating report...")

        # Build timeline
        timeline = self._build_timeline(signals)

        # Build signal summary
        signal_summary = self._build_signal_summary(signals)

        # Determine going concern status
        gc_status = self._determine_going_concern_status(signals)

        # Calculate timeline context
        timeline_context = self._calculate_timeline_context(signals)

        # Build validation stats
        validation = {
            "total_extracted": len(signals) + len(rejected_signals),
            "total_validated": len(signals),
            "total_rejected": len(rejected_signals),
            "validation_rate": len(signals) / (len(signals) + len(rejected_signals))
            if (len(signals) + len(rejected_signals)) > 0 else 0,
        }

        # Sort signals by date (newest first)
        sorted_signals = sorted(
            signals,
            key=lambda x: x.get("date", ""),
            reverse=True,
        )

        if update_callback:
            await update_callback("Report generation complete")

        return AnalysisReport(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            status="ACTIVE",
            signal_count=len(signals),
            signal_summary=signal_summary,
            signals=sorted_signals,
            timeline=timeline,
            going_concern_status=gc_status["status"],
            going_concern_first_seen=gc_status.get("first_seen"),
            going_concern_last_seen=gc_status.get("last_seen"),
            first_signal_date=timeline_context.get("first_signal_date"),
            last_signal_date=timeline_context.get("last_signal_date"),
            days_since_last_signal=timeline_context.get("days_since_last_signal"),
            validation=validation,
            filings_analyzed=filings_analyzed,
            analyzed_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
        )

    def _build_timeline(self, signals: List[Dict[str, Any]]) -> List[TimelineEvent]:
        """Build chronological timeline of signals."""
        timeline = []

        for signal in signals:
            # Truncate evidence for timeline view
            evidence = signal.get("evidence", "")
            if len(evidence) > 300:
                evidence = evidence[:300] + "..."

            timeline.append(TimelineEvent(
                date=signal.get("date", ""),
                type=signal.get("type", ""),
                evidence=evidence,
                filing_type=signal.get("filing_type", ""),
                filing_accession=signal.get("filing_accession", ""),
                item_number=signal.get("item_number", ""),
            ))

        # Sort by date (newest first)
        timeline.sort(key=lambda x: x.date, reverse=True)

        return timeline

    def _build_signal_summary(self, signals: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count signals by type."""
        summary = {}
        for signal in signals:
            signal_type = signal.get("type", "UNKNOWN")
            summary[signal_type] = summary.get(signal_type, 0) + 1
        return summary

    def _determine_going_concern_status(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Determine going concern status based on signal history.

        Returns:
        - status: "ACTIVE" | "REMOVED" | "NEVER"
        - first_seen: date when first appeared
        - last_seen: date when last appeared
        """
        gc_signals = [s for s in signals if s.get("type") == "GOING_CONCERN"]

        if not gc_signals:
            return {"status": "NEVER"}

        # Sort by date
        gc_signals_sorted = sorted(
            [s for s in gc_signals if s.get("date")],
            key=lambda x: x["date"]
        )

        if not gc_signals_sorted:
            return {"status": "NEVER"}

        first_seen = gc_signals_sorted[0]["date"]
        last_seen = gc_signals_sorted[-1]["date"]

        # Determine if going concern is still active
        try:
            last_gc_date = datetime.fromisoformat(
                last_seen.replace("Z", "").replace("T", " ").split("+")[0].split(" ")[0]
            )
            days_since = (datetime.now() - last_gc_date).days

            # If last going concern was more than 15 months ago, likely removed
            if days_since > 450:
                return {
                    "status": "REMOVED",
                    "first_seen": first_seen[:10] if first_seen else None,
                    "last_seen": last_seen[:10] if last_seen else None,
                }
            else:
                return {
                    "status": "ACTIVE",
                    "first_seen": first_seen[:10] if first_seen else None,
                    "last_seen": last_seen[:10] if last_seen else None,
                }
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing going concern dates: {e}")
            return {
                "status": "ACTIVE",
                "first_seen": first_seen[:10] if first_seen else None,
                "last_seen": last_seen[:10] if last_seen else None,
            }

    def _calculate_timeline_context(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculate timeline context (first/last signal, days since)."""
        if not signals:
            return {}

        # Get valid dates
        valid_signals = [s for s in signals if s.get("date")]
        if not valid_signals:
            return {}

        sorted_signals = sorted(valid_signals, key=lambda x: x["date"])
        first_date = sorted_signals[0]["date"][:10]
        last_date = sorted_signals[-1]["date"][:10]

        # Calculate days since last signal
        try:
            last_dt = datetime.fromisoformat(last_date)
            days_since = (datetime.now() - last_dt).days
        except (ValueError, TypeError):
            days_since = None

        return {
            "first_signal_date": first_date,
            "last_signal_date": last_date,
            "days_since_last_signal": days_since,
        }

    def to_dict(self, report: AnalysisReport) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "ticker": report.ticker,
            "cik": report.cik,
            "company_name": report.company_name,
            "status": report.status,
            "signal_count": report.signal_count,
            "signal_summary": report.signal_summary,
            "signals": report.signals,
            "timeline": [asdict(t) for t in report.timeline],
            "going_concern_status": report.going_concern_status,
            "going_concern_first_seen": report.going_concern_first_seen,
            "going_concern_last_seen": report.going_concern_last_seen,
            "first_signal_date": report.first_signal_date,
            "last_signal_date": report.last_signal_date,
            "days_since_last_signal": report.days_since_last_signal,
            "validation": report.validation,
            "filings_analyzed": report.filings_analyzed,
            "analyzed_at": report.analyzed_at,
            "expires_at": report.expires_at,
        }


# Singleton instance
reporter_agent = ReportGeneratorAgent()
