"""Agent 4: Risk Scorer - Calculates bankruptcy risk score with predictive weights and combinations."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.services.neo4j_service import neo4j_service
from app.tools.scoring import risk_scorer
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SignalContribution:
    """Individual signal's contribution to risk score."""
    signal_type: str
    predictive_weight: int
    severity: int
    contribution: float


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
class CombinationPattern:
    """Detected dangerous signal combination."""
    pattern: str
    signals: List[str]
    multiplier: float
    description: str
    risk_level: str


@dataclass
class RiskAssessment:
    """Complete risk assessment output."""
    ticker: str
    risk_score: int
    risk_level: str
    base_score: int
    combination_bonus: int
    velocity_bonus: int
    signal_contributions: List[SignalContribution]
    combinations_detected: List[CombinationPattern]
    velocity_info: Dict[str, Any]
    pattern_matches: List[PatternMatch]
    similar_companies: List[SimilarCompany]
    assessment_notes: str
    error: Optional[str] = None


class RiskScorerAgent:
    """
    Agent 4: Bankruptcy Risk Assessment Specialist

    Calculates risk scores using:
    - Predictive weights (not just severity)
    - Signal combinations (patterns that predict bankruptcy)
    - Signal velocity (how fast signals are accumulating)
    - Pattern matching against known bankruptcies (Neo4j)
    """

    def __init__(self):
        self.role = "Bankruptcy Risk Assessment Specialist"
        self.goal = "Calculate predictive risk scores from distress signals"

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
            # Step 1: Calculate comprehensive risk score using new scoring
            score_result = risk_scorer.calculate_risk_score(signals)

            if update_callback:
                msg = f"Base score: {score_result['base_score']} from {len(signals)} signals"
                if score_result['combination_bonus'] > 0:
                    msg += f" | Combo bonus: +{score_result['combination_bonus']}"
                if score_result['velocity_bonus'] > 0:
                    msg += f" | Velocity bonus: +{score_result['velocity_bonus']}"
                await update_callback(msg)

            # Convert signal breakdown to SignalContribution objects
            signal_contributions = [
                SignalContribution(
                    signal_type=s["type"],
                    predictive_weight=s["predictive_weight"],
                    severity=s["severity"],
                    contribution=s["contribution"],
                )
                for s in score_result["signal_breakdown"]
            ]

            # Convert combinations to CombinationPattern objects
            combinations_detected = [
                CombinationPattern(
                    pattern=c["pattern"],
                    signals=c["signals"],
                    multiplier=c["multiplier"],
                    description=c["description"],
                    risk_level=c["risk_level"],
                )
                for c in score_result["combinations_detected"]
            ]

            # Log combination detections
            if combinations_detected:
                combo_names = [c.pattern for c in combinations_detected]
                logger.info(f"Risk patterns detected: {', '.join(combo_names)}")
                if update_callback:
                    await update_callback(f"Detected patterns: {', '.join(combo_names)}")

            # Log velocity
            velocity_info = score_result["velocity_info"]
            if velocity_info.get("velocity") != "LOW":
                logger.info(
                    f"Signal velocity: {velocity_info['velocity']} "
                    f"({velocity_info['signals_per_90_days']} signals in 90 days)"
                )

            # Step 2: Find pattern matches to known bankruptcies (Neo4j)
            pattern_matches = await self._find_bankruptcy_patterns(ticker)
            neo4j_bonus = self._calculate_pattern_bonus(pattern_matches)

            if update_callback and pattern_matches:
                await update_callback(
                    f"Found {len(pattern_matches)} bankruptcy pattern matches"
                )

            # Step 3: Find similar companies (Neo4j)
            similar_companies = await self._find_similar_companies(ticker)

            if update_callback and similar_companies:
                await update_callback(
                    f"Found {len(similar_companies)} similar companies"
                )

            # Step 4: Calculate final score (include Neo4j bonus)
            final_score = min(100, score_result["score"] + int(neo4j_bonus))
            risk_level = score_result["level"]
            if final_score >= 70:
                risk_level = "CRITICAL"
            elif final_score >= 50:
                risk_level = "HIGH"

            # Step 5: Update company risk score in Neo4j
            await self._update_company_risk_score(ticker, final_score)

            # Generate assessment notes
            notes = self._generate_assessment_notes(
                signals,
                signal_contributions,
                combinations_detected,
                velocity_info,
                pattern_matches,
                final_score,
            )

            logger.info(
                f"Risk score for {ticker}: {final_score} ({risk_level}) "
                f"[base: {score_result['base_score']}, combo: +{score_result['combination_bonus']}, "
                f"velocity: +{score_result['velocity_bonus']}, neo4j: +{int(neo4j_bonus)}]"
            )

            if update_callback:
                await update_callback(
                    f"Risk assessment complete: {final_score}/100 ({risk_level})"
                )

            return RiskAssessment(
                ticker=ticker,
                risk_score=final_score,
                risk_level=risk_level,
                base_score=score_result["base_score"],
                combination_bonus=score_result["combination_bonus"],
                velocity_bonus=score_result["velocity_bonus"],
                signal_contributions=signal_contributions,
                combinations_detected=combinations_detected,
                velocity_info=velocity_info,
                pattern_matches=pattern_matches,
                similar_companies=similar_companies,
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
                base_score=base_score,
                combination_bonus=0,
                velocity_bonus=0,
                signal_contributions=[],
                combinations_detected=[],
                velocity_info={"velocity": "LOW", "multiplier": 1.0},
                pattern_matches=[],
                similar_companies=[],
                assessment_notes="Risk calculated with basic method due to error",
                error=str(e),
            )

    def _calculate_simple_score(self, signals: List[Dict[str, Any]]) -> int:
        """Simple fallback score calculation."""
        from app.core.constants import PREDICTIVE_WEIGHTS, BASE_SEVERITY

        score = 0
        for signal in signals:
            signal_type = signal.get("type", "")
            severity = signal.get("severity", BASE_SEVERITY.get(signal_type, 5))
            weight = PREDICTIVE_WEIGHTS.get(signal_type, 5)
            score += weight * (severity / 10.0)

        # Normalize to 0-100
        max_possible = len(signals) * 10 if signals else 1
        normalized = (score / max_possible) * 100
        return min(100, int(normalized))

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
                f"Neo4j pattern bonus: +{bonus:.1f} from match to {best_match.ticker} "
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
            return "ELEVATED"
        return "LOW"

    def _generate_assessment_notes(
        self,
        signals: List[Dict[str, Any]],
        contributions: List[SignalContribution],
        combinations: List[CombinationPattern],
        velocity_info: Dict[str, Any],
        pattern_matches: List[PatternMatch],
        final_score: int,
    ) -> str:
        """Generate human-readable assessment notes."""
        notes = []

        # Combination pattern warnings (most important)
        if combinations:
            critical_combos = [c for c in combinations if c.risk_level == "CRITICAL"]
            if critical_combos:
                combo_names = [c.pattern.replace("_", " ").title() for c in critical_combos]
                notes.append(f"CRITICAL PATTERNS: {', '.join(combo_names)}")

        # Velocity warning
        if velocity_info.get("velocity") == "EXTREME":
            notes.append(
                f"EXTREME VELOCITY: {velocity_info['signals_per_90_days']} signals in 90 days"
            )
        elif velocity_info.get("velocity") == "HIGH":
            notes.append(
                f"High velocity: {velocity_info['signals_per_90_days']} signals in 90 days"
            )

        # Top contributors
        if contributions:
            top_contributors = contributions[:3]
            top_types = [c.signal_type.replace("_", " ").title() for c in top_contributors]
            notes.append(f"Top risk factors: {', '.join(top_types)}")

        # Pattern match warning (Neo4j)
        if pattern_matches:
            best = max(pattern_matches, key=lambda x: x.similarity_score)
            if best.similarity_score > 0.6:
                notes.append(
                    f"Pattern {best.similarity_score:.0%} similar to {best.name} (bankrupt)"
                )

        # Overall assessment
        if final_score >= 70:
            notes.append("CRITICAL: Multiple severe distress indicators present")
        elif final_score >= 50:
            notes.append("HIGH: Significant warning signs detected")
        elif final_score >= 30:
            notes.append("ELEVATED: Some concerns warrant monitoring")
        else:
            notes.append("LOW: Limited distress indicators")

        return "; ".join(notes)


# Singleton instance
scorer_agent = RiskScorerAgent()
