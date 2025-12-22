"""Agent 5: Report Generator - Generates final analysis report."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from app.agents.scorer import RiskAssessment, SignalContribution, PatternMatch, SimilarCompany
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TimelineEvent:
    """Event in the signal timeline."""
    date: str
    type: str
    severity: int
    confidence: float
    evidence: str
    filing_type: str
    item_number: str


@dataclass
class RiskBreakdown:
    """Breakdown of risk by category."""
    category: str
    signals: int
    contribution: float
    percentage: float


@dataclass
class AnalysisReport:
    """Complete analysis report for frontend."""
    # Company info
    ticker: str
    cik: str
    company_name: str
    status: str

    # Risk assessment
    risk_score: int
    risk_level: str

    # Signal data
    signal_count: int
    signal_summary: Dict[str, int]
    signals: List[Dict[str, Any]]
    timeline: List[TimelineEvent]
    risk_breakdown: List[RiskBreakdown]

    # Pattern matching
    similar_companies: List[Dict[str, Any]]
    bankruptcy_pattern_match: Optional[Dict[str, Any]]

    # Narrative
    executive_summary: str
    key_risks: List[str]
    assessment_notes: str

    # Validation stats
    validation: Dict[str, Any]

    # Metadata
    filings_analyzed: int
    analyzed_at: str
    expires_at: str


class ReportGeneratorAgent:
    """
    Agent 5: Financial Report Writer

    Role: Generate clear, actionable analysis reports
    Goal: Create comprehensive reports for investors
    Backstory: Former equity research analyst who wrote reports for institutional investors
    """

    def __init__(self):
        self.role = "Financial Report Writer"
        self.goal = "Create clear, actionable analysis reports for investors"
        self.backstory = "Former equity research analyst who wrote reports for institutional investors"

    async def run(
        self,
        ticker: str,
        cik: str,
        company_name: str,
        signals: List[Dict[str, Any]],
        rejected_signals: List[Dict[str, Any]],
        risk_assessment: RiskAssessment,
        filings_analyzed: int,
        update_callback=None,
    ) -> AnalysisReport:
        """
        Generate final analysis report.

        Args:
            ticker: Stock ticker
            cik: Company CIK
            company_name: Company name
            signals: Validated signals
            rejected_signals: Signals that failed validation
            risk_assessment: Risk assessment from scorer agent
            filings_analyzed: Number of filings analyzed
            update_callback: Optional callback for progress updates

        Returns:
            AnalysisReport for frontend consumption
        """
        if update_callback:
            await update_callback("Generating report...")

        # Build timeline
        timeline = self._build_timeline(signals)

        # Build signal summary
        signal_summary = self._build_signal_summary(signals)

        # Build risk breakdown by category
        risk_breakdown = self._build_risk_breakdown(
            risk_assessment.signal_contributions
        )

        # Format similar companies
        similar_companies = self._format_similar_companies(
            risk_assessment.similar_companies
        )

        # Format bankruptcy pattern match
        bankruptcy_match = self._format_pattern_match(
            risk_assessment.pattern_matches
        )

        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            company_name,
            ticker,
            signals,
            risk_assessment,
        )

        # Extract key risks
        key_risks = self._extract_key_risks(
            signals,
            risk_assessment.signal_contributions,
        )

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
            risk_score=risk_assessment.risk_score,
            risk_level=risk_assessment.risk_level,
            signal_count=len(signals),
            signal_summary=signal_summary,
            signals=sorted_signals,
            timeline=timeline,
            risk_breakdown=risk_breakdown,
            similar_companies=similar_companies,
            bankruptcy_pattern_match=bankruptcy_match,
            executive_summary=executive_summary,
            key_risks=key_risks,
            assessment_notes=risk_assessment.assessment_notes,
            validation=validation,
            filings_analyzed=filings_analyzed,
            analyzed_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow().replace(day=datetime.utcnow().day + 7)).isoformat(),
        )

    def _build_timeline(self, signals: List[Dict[str, Any]]) -> List[TimelineEvent]:
        """Build chronological timeline of signals."""
        timeline = []

        for signal in signals:
            # Truncate evidence for timeline view
            evidence = signal.get("evidence", "")
            if len(evidence) > 200:
                evidence = evidence[:200] + "..."

            timeline.append(TimelineEvent(
                date=signal.get("date", ""),
                type=signal.get("type", ""),
                severity=signal.get("severity", 5),
                confidence=signal.get("confidence", 0.8),
                evidence=evidence,
                filing_type=signal.get("filing_type", ""),
                item_number=signal.get("item_number", ""),
            ))

        # Sort by date (newest first)
        timeline.sort(key=lambda x: x.date, reverse=True)

        # Limit to 20 events
        return timeline[:20]

    def _build_signal_summary(self, signals: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count signals by type."""
        summary = {}
        for signal in signals:
            signal_type = signal.get("type", "UNKNOWN")
            summary[signal_type] = summary.get(signal_type, 0) + 1
        return summary

    def _build_risk_breakdown(
        self, contributions: List[SignalContribution]
    ) -> List[RiskBreakdown]:
        """Build risk breakdown by category."""
        # Define categories
        categories = {
            "Financial": ["GOING_CONCERN", "DEBT_DEFAULT", "COVENANT_VIOLATION", "CREDIT_DOWNGRADE", "EQUITY_DILUTION"],
            "Governance": ["CEO_DEPARTURE", "CFO_DEPARTURE", "BOARD_RESIGNATION", "AUDITOR_CHANGE"],
            "Operational": ["MASS_LAYOFFS", "ASSET_SALE", "RESTRUCTURING"],
            "Regulatory": ["DELISTING_WARNING", "SEC_INVESTIGATION", "MATERIAL_WEAKNESS"],
        }

        # Calculate contributions by category
        category_data = {}
        total_contribution = sum(c.contribution for c in contributions)

        for category, types in categories.items():
            cat_contributions = [
                c for c in contributions if c.signal_type in types
            ]
            if cat_contributions:
                category_data[category] = {
                    "signals": len(cat_contributions),
                    "contribution": sum(c.contribution for c in cat_contributions),
                }

        # Build breakdown
        breakdown = []
        for category, data in category_data.items():
            breakdown.append(RiskBreakdown(
                category=category,
                signals=data["signals"],
                contribution=round(data["contribution"], 1),
                percentage=round(data["contribution"] / total_contribution * 100, 1)
                if total_contribution > 0 else 0,
            ))

        # Sort by contribution
        breakdown.sort(key=lambda x: x.contribution, reverse=True)
        return breakdown

    def _format_similar_companies(
        self, similar: List[SimilarCompany]
    ) -> List[Dict[str, Any]]:
        """Format similar companies for output."""
        return [
            {
                "ticker": s.ticker,
                "name": s.name,
                "status": s.status,
                "risk_score": s.risk_score,
                "common_signals": s.common_signals,
                "common_signal_types": s.common_signal_types,
                "similarity_score": round(s.similarity_score, 2),
            }
            for s in similar
        ]

    def _format_pattern_match(
        self, matches: List[PatternMatch]
    ) -> Optional[Dict[str, Any]]:
        """Format the best bankruptcy pattern match."""
        if not matches:
            return None

        # Get best match
        best = max(matches, key=lambda x: x.similarity_score)

        if best.similarity_score < 0.3:
            return None

        return {
            "matched_company": best.ticker,
            "company_name": best.name,
            "bankruptcy_date": best.bankruptcy_date,
            "matching_signals": best.matching_signals,
            "match_count": best.match_count,
            "similarity_score": round(best.similarity_score, 2),
        }

    def _generate_executive_summary(
        self,
        company_name: str,
        ticker: str,
        signals: List[Dict[str, Any]],
        risk_assessment: RiskAssessment,
    ) -> str:
        """Generate executive summary paragraph."""
        risk_score = risk_assessment.risk_score
        risk_level = risk_assessment.risk_level

        if not signals:
            return (
                f"Analysis of {company_name} ({ticker}) found no significant distress "
                f"signals in recent SEC filings. Risk score: {risk_score}/100 ({risk_level}). "
                f"The company does not currently exhibit patterns associated with bankruptcy risk."
            )

        # Count signal types
        signal_types = {}
        for s in signals:
            t = s.get("type", "")
            signal_types[t] = signal_types.get(t, 0) + 1

        # Top signals
        top_signals = sorted(signal_types.items(), key=lambda x: x[1], reverse=True)[:3]
        signal_text = ", ".join(
            f"{count} {stype.replace('_', ' ').lower()}"
            for stype, count in top_signals
        )

        # Risk description
        if risk_level == "CRITICAL":
            risk_desc = (
                "Multiple critical distress indicators have been detected, suggesting "
                "elevated bankruptcy risk. Immediate attention is warranted."
            )
        elif risk_level == "HIGH":
            risk_desc = (
                "Significant warning signs are present that warrant close monitoring. "
                "The company exhibits patterns seen in distressed corporations."
            )
        elif risk_level == "MEDIUM":
            risk_desc = (
                "Some concerns have been identified that should be monitored. "
                "The company shows moderate distress indicators."
            )
        else:
            risk_desc = (
                "Limited distress indicators are present. "
                "The company does not show significant bankruptcy warning signs."
            )

        # Pattern match warning
        pattern_warning = ""
        if risk_assessment.pattern_matches:
            best = max(risk_assessment.pattern_matches, key=lambda x: x.similarity_score)
            if best.similarity_score > 0.5:
                pattern_warning = (
                    f" Notably, the signal pattern shows {best.similarity_score:.0%} "
                    f"similarity to {best.name} prior to its bankruptcy filing."
                )

        return (
            f"Analysis of {company_name} ({ticker}) identified {len(signals)} validated "
            f"distress signals including {signal_text}. Risk score: {risk_score}/100 ({risk_level}). "
            f"{risk_desc}{pattern_warning}"
        )

    def _extract_key_risks(
        self,
        signals: List[Dict[str, Any]],
        contributions: List[SignalContribution],
    ) -> List[str]:
        """Extract key risk factors as bullet points."""
        key_risks = []

        # Get top contributing signal types
        seen_types = set()
        for contrib in contributions[:5]:
            if contrib.signal_type not in seen_types:
                seen_types.add(contrib.signal_type)

                # Find matching signal for context
                matching = [s for s in signals if s.get("type") == contrib.signal_type]
                if matching:
                    signal = matching[0]
                    risk_text = self._format_risk_point(
                        contrib.signal_type,
                        signal,
                        contrib.contribution,
                    )
                    key_risks.append(risk_text)

        return key_risks[:5]

    def _format_risk_point(
        self,
        signal_type: str,
        signal: Dict[str, Any],
        contribution: float,
    ) -> str:
        """Format a single risk point."""
        type_name = signal_type.replace("_", " ").title()
        date = signal.get("date", "")
        severity = signal.get("severity", 5)

        severity_desc = ""
        if severity >= 8:
            severity_desc = "Critical"
        elif severity >= 6:
            severity_desc = "High"
        elif severity >= 4:
            severity_desc = "Moderate"
        else:
            severity_desc = "Low"

        if date:
            return f"{type_name} ({severity_desc} severity, {date})"
        return f"{type_name} ({severity_desc} severity)"

    def to_dict(self, report: AnalysisReport) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        result = {
            "ticker": report.ticker,
            "cik": report.cik,
            "company_name": report.company_name,
            "status": report.status,
            "risk_score": report.risk_score,
            "risk_level": report.risk_level,
            "signal_count": report.signal_count,
            "signal_summary": report.signal_summary,
            "signals": report.signals,
            "timeline": [asdict(t) for t in report.timeline],
            "risk_breakdown": [asdict(r) for r in report.risk_breakdown],
            "similar_companies": report.similar_companies,
            "bankruptcy_pattern_match": report.bankruptcy_pattern_match,
            "executive_summary": report.executive_summary,
            "key_risks": report.key_risks,
            "assessment_notes": report.assessment_notes,
            "validation": report.validation,
            "filings_analyzed": report.filings_analyzed,
            "analyzed_at": report.analyzed_at,
            "expires_at": report.expires_at,
        }
        return result


# Singleton instance
reporter_agent = ReportGeneratorAgent()
