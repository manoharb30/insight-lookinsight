"""Agent 4: Risk Scorer - Calculates bankruptcy risk score with pattern matching."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.services.neo4j_service import neo4j_service
from app.core.logging import get_logger

logger = get_logger(__name__)


# Signal weights for risk calculation
SIGNAL_WEIGHTS = {
    "GOING_CONCERN": 25,
    "DEBT_DEFAULT": 20,
    "DELISTING_WARNING": 15,
    "MASS_LAYOFFS": 15,
    "COVENANT_VIOLATION": 12,
    "CEO_DEPARTURE": 10,
    "CFO_DEPARTURE": 10,
    "CREDIT_DOWNGRADE": 10,
    "RESTRUCTURING": 10,
    "AUDITOR_CHANGE": 8,
    "SEC_INVESTIGATION": 8,
    "ASSET_SALE": 8,
    "MATERIAL_WEAKNESS": 5,
    "BOARD_RESIGNATION": 5,
    "EQUITY_DILUTION": 5,
}


@dataclass
class SignalContribution:
    """Individual signal's contribution to risk score."""
    signal_type: str
    base_weight: int
    severity_mult: float
    recency_mult: float
    confidence_mult: float
    contribution: float
    date: str


@dataclass
class PatternMatch:
    """Match against a known bankruptcy case."""
    ticker: str
    name: str
    bankruptcy_date: Optional[str]
    matching_signals: List[str]
    match_count: int
    similarity_score: float


@dataclass
class SimilarCompany:
    """Company with similar signal pattern."""
    ticker: str
    name: str
    status: str
    risk_score: int
    common_signals: int
    common_signal_types: List[str]
    similarity_score: float


@dataclass
class RiskAssessment:
    """Complete risk assessment output."""
    ticker: str
    risk_score: int
    risk_level: str
    signal_contributions: List[SignalContribution]
    pattern_matches: List[PatternMatch]
    similar_companies: List[SimilarCompany]
    pattern_bonus: float
    assessment_notes: str
    error: Optional[str] = None


class RiskScorerAgent:
    """
    Agent 4: Bankruptcy Risk Assessment Specialist

    Role: Calculate overall risk based on signal patterns
    Goal: Provide accurate risk score with pattern matching insights
    Backstory: Quantitative analyst who has studied 500+ corporate bankruptcies
    """

    def __init__(self):
        self.role = "Bankruptcy Risk Assessment Specialist"
        self.goal = "Calculate probability of bankruptcy based on signal patterns"
        self.backstory = "Quantitative analyst who has studied 500+ corporate bankruptcies"

    async def run(
        self,
        ticker: str,
        signals: List[Dict[str, Any]],
        update_callback=None,
    ) -> RiskAssessment:
        """
        Calculate risk score for a company based on validated signals.

        Args:
            ticker: Stock ticker
            signals: List of validated signals
            update_callback: Optional callback for progress updates

        Returns:
            RiskAssessment with score, contributions, and pattern matches
        """
        if update_callback:
            await update_callback("Calculating risk score...")

        try:
            # Step 1: Calculate base risk score from signals
            contributions, base_score = self._calculate_base_score(signals)

            if update_callback:
                await update_callback(f"Base score: {base_score:.1f} from {len(signals)} signals")

            # Step 2: Find pattern matches to known bankruptcies
            pattern_matches = await self._find_bankruptcy_patterns(ticker)
            pattern_bonus = self._calculate_pattern_bonus(pattern_matches)

            if update_callback and pattern_matches:
                await update_callback(
                    f"Found {len(pattern_matches)} bankruptcy pattern matches"
                )

            # Step 3: Find similar companies
            similar_companies = await self._find_similar_companies(ticker)

            if update_callback and similar_companies:
                await update_callback(
                    f"Found {len(similar_companies)} similar companies"
                )

            # Step 4: Calculate final score
            final_score = min(100, int(base_score + pattern_bonus))
            risk_level = self._get_risk_level(final_score)

            # Step 5: Update company risk score in Neo4j
            await self._update_company_risk_score(ticker, final_score)

            # Generate assessment notes
            notes = self._generate_assessment_notes(
                signals, contributions, pattern_matches, final_score
            )

            if update_callback:
                await update_callback(
                    f"Risk assessment complete: {final_score}/100 ({risk_level})"
                )

            return RiskAssessment(
                ticker=ticker,
                risk_score=final_score,
                risk_level=risk_level,
                signal_contributions=contributions,
                pattern_matches=pattern_matches,
                similar_companies=similar_companies,
                pattern_bonus=pattern_bonus,
                assessment_notes=notes,
            )

        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            # Return basic assessment on error
            base_score = self._calculate_simple_score(signals)
            return RiskAssessment(
                ticker=ticker,
                risk_score=base_score,
                risk_level=self._get_risk_level(base_score),
                signal_contributions=[],
                pattern_matches=[],
                similar_companies=[],
                pattern_bonus=0,
                assessment_notes="Risk calculated with basic method due to error",
                error=str(e),
            )

    def _calculate_base_score(
        self, signals: List[Dict[str, Any]]
    ) -> tuple[List[SignalContribution], float]:
        """Calculate base risk score from signals with weights."""
        contributions = []
        total_score = 0.0

        for signal in signals:
            signal_type = signal.get("type", "")
            severity = signal.get("severity", 5)
            confidence = signal.get("confidence", 0.8)
            date_str = signal.get("date", "")

            # Get base weight
            base_weight = SIGNAL_WEIGHTS.get(signal_type, 5)

            # Severity multiplier (1-10 scale, normalize to 0.1-1.0)
            severity_mult = severity / 10.0

            # Confidence multiplier
            confidence_mult = confidence

            # Recency multiplier
            recency_mult = self._calculate_recency_weight(date_str)

            # Calculate contribution
            contribution = base_weight * severity_mult * confidence_mult * recency_mult
            total_score += contribution

            contributions.append(SignalContribution(
                signal_type=signal_type,
                base_weight=base_weight,
                severity_mult=severity_mult,
                recency_mult=recency_mult,
                confidence_mult=confidence_mult,
                contribution=round(contribution, 2),
                date=date_str,
            ))

        # Sort by contribution (highest first)
        contributions.sort(key=lambda x: x.contribution, reverse=True)

        return contributions, total_score

    def _calculate_recency_weight(self, date_str: str) -> float:
        """Calculate recency weight - recent signals count more."""
        if not date_str:
            return 1.0

        try:
            signal_date = datetime.strptime(date_str, "%Y-%m-%d")
            days_ago = (datetime.now() - signal_date).days

            if days_ago <= 180:  # Last 6 months
                return 1.5
            elif days_ago <= 365:  # 6-12 months
                return 1.0
            elif days_ago <= 730:  # 1-2 years
                return 0.7
            else:
                return 0.5
        except ValueError:
            return 1.0

    def _calculate_simple_score(self, signals: List[Dict[str, Any]]) -> int:
        """Simple fallback score calculation."""
        score = 0
        for signal in signals:
            signal_type = signal.get("type", "")
            severity = signal.get("severity", 5)
            weight = SIGNAL_WEIGHTS.get(signal_type, 5)
            score += weight * (severity / 7.0)
        return min(100, int(score))

    async def _find_bankruptcy_patterns(self, ticker: str) -> List[PatternMatch]:
        """Query Neo4j for pattern matches against known bankruptcies."""
        try:
            matches = await neo4j_service.match_bankruptcy_patterns(ticker)
            return [
                PatternMatch(
                    ticker=m.get("ticker", ""),
                    name=m.get("name", ""),
                    bankruptcy_date=str(m.get("bankruptcy_date", "")) if m.get("bankruptcy_date") else None,
                    matching_signals=m.get("common_signal_types", []),
                    match_count=m.get("matching_signals", 0),
                    similarity_score=m.get("similarity_score", 0),
                )
                for m in matches
            ]
        except Exception as e:
            logger.warning(f"Error finding bankruptcy patterns: {e}")
            return []

    async def _find_similar_companies(self, ticker: str) -> List[SimilarCompany]:
        """Find companies with similar signal patterns."""
        try:
            similar = await neo4j_service.find_similar_companies(ticker, limit=5)
            return [
                SimilarCompany(
                    ticker=s.get("ticker", ""),
                    name=s.get("name", ""),
                    status=s.get("status", "ACTIVE"),
                    risk_score=s.get("risk_score", 0) or 0,
                    common_signals=s.get("common_signals", 0),
                    common_signal_types=s.get("common_signal_types", []),
                    similarity_score=s.get("similarity_score", 0),
                )
                for s in similar
            ]
        except Exception as e:
            logger.warning(f"Error finding similar companies: {e}")
            return []

    def _calculate_pattern_bonus(self, pattern_matches: List[PatternMatch]) -> float:
        """Calculate bonus score based on pattern matches to bankruptcies."""
        if not pattern_matches:
            return 0.0

        # Take the highest similarity match
        best_match = max(pattern_matches, key=lambda x: x.similarity_score)

        # If similarity > 50%, add bonus
        if best_match.similarity_score > 0.5:
            bonus = 10 * best_match.similarity_score
            logger.info(
                f"Pattern bonus: +{bonus:.1f} from match to {best_match.ticker} "
                f"({best_match.similarity_score:.0%} similarity)"
            )
            return bonus

        return 0.0

    async def _update_company_risk_score(self, ticker: str, score: int) -> None:
        """Update the company's risk score in Neo4j."""
        try:
            await neo4j_service.store_company({
                "ticker": ticker,
                "risk_score": score,
                "status": "ACTIVE",
            })
        except Exception as e:
            logger.warning(f"Error updating company risk score: {e}")

    def _get_risk_level(self, score: int) -> str:
        """Convert numeric score to risk level."""
        if score >= 70:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 30:
            return "MEDIUM"
        return "LOW"

    def _generate_assessment_notes(
        self,
        signals: List[Dict[str, Any]],
        contributions: List[SignalContribution],
        pattern_matches: List[PatternMatch],
        final_score: int,
    ) -> str:
        """Generate human-readable assessment notes."""
        notes = []

        # Signal summary
        if contributions:
            top_contributors = contributions[:3]
            top_types = [c.signal_type.replace("_", " ").title() for c in top_contributors]
            notes.append(f"Top risk factors: {', '.join(top_types)}")

        # Pattern match warning
        if pattern_matches:
            best = max(pattern_matches, key=lambda x: x.similarity_score)
            if best.similarity_score > 0.6:
                notes.append(
                    f"WARNING: Signal pattern {best.similarity_score:.0%} similar to "
                    f"{best.name} ({best.ticker}) which filed bankruptcy"
                )

        # Recency warning
        recent_signals = [
            s for s in signals
            if s.get("date") and self._calculate_recency_weight(s.get("date", "")) >= 1.5
        ]
        if recent_signals:
            notes.append(f"{len(recent_signals)} signals detected in last 6 months")

        # Overall assessment
        if final_score >= 70:
            notes.append("CRITICAL: Multiple severe distress indicators present")
        elif final_score >= 50:
            notes.append("HIGH: Significant warning signs detected")
        elif final_score >= 30:
            notes.append("MEDIUM: Some concerns warrant monitoring")
        else:
            notes.append("LOW: Limited distress indicators")

        return "; ".join(notes)


# Singleton instance
scorer_agent = RiskScorerAgent()
